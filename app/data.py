import base64
import datetime
import json
import logging
import socket
from io import BytesIO

import requests
from PIL import Image
from fdb import ISOLATION_LEVEL_READ_COMMITED_RO

from indexer import tools

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection cache
_connection_cache = {}

# Channel cache for clientinfo
_channel_cache = {'channel': 'ices', 'last_update': 0.0}
CACHE_TIMEOUT = 60  # Cache channel for 60 seconds

# Metadata cache
_meta_cache = {'data': None, 'last_update': 0.0}
META_CACHE_TIMEOUT = 5  # Cache metadata for 5 seconds

ro_transaction = None


def get_connection(connection_type='default'):
    """Get a cached database connection or create a new one if not exists.

    Args:
        connection_type (str): Type of connection to get ('default', 'secondary', or 'tertiary')

    Returns:
        Connection object
    """
    global ro_transaction
    if connection_type not in _connection_cache:
        connection = tools.get_connector()

        if connection_type == 'default':
            _connection_cache[connection_type] = connection.getconnection()
            ro_transaction = _connection_cache[connection_type].trans(ISOLATION_LEVEL_READ_COMMITED_RO)

    return _connection_cache[connection_type]


def call_procedure(name, param=None):
    try:
        con = get_connection("default")
        with (con.trans()) as tr:
            cura = tr.cursor()
            if param is not None:
                cura.callproc(name, [param])
            else:
                cura.callproc(name)

            if param is not None:
                logger.info(f"Called procedure {name} with Parameter: {param}")
            else:
                logger.info(f"Called procedure {name}")
    except Exception as e:
        logger.error(f"Error in call_procedure ({name}): {e}")


'''Query (evtl. mit Parametern) ausfuehren, standardmaessig alles zurueckliefern, ausser one ist True
'''


def query_db_header(query, args=(), one=False):
    """Execute a query and return results as a dictionary with column names as keys.

    Args:
        query (str): SQL query to execute
        args (tuple): Parameters for the query
        one (bool): If True, return only the first result

    Returns:
        dict or list of dicts: Query results
    """
    try:
        con = get_connection('default')
        with con.trans() as tr:
            cur = tr.cursor()
            cur.execute(query, args)
            cur.set_stream_blob_treshold(-1)
            r = [dict((cur.description[i][0], value) for i, value in enumerate(row)) for row in cur.fetchall()]
        return (r[0] if r else None) if one else r
    except Exception as e:
        logger.error(f"Error in query_db_header: {e}")
        logger.error(f"Query: {query}, Args: {args}")
        return None


def query_db_ro(query, args=(), one=False):
    """Execute a query and return raw results.

    Args:
        query (str): SQL query to execute
        args (tuple): Parameters for the query
        one (bool): If True, return only the first result

    Returns:
        tuple or list of tuples: Query results
    """
    try:
        con = get_connection('default')

        # and cursor

        cur = ro_transaction.cursor()
        cur.execute(query, args)
        cur.set_stream_blob_treshold(-1)
        r = cur.fetchone() if one else cur.fetchall()
        return r if r else None
    except Exception as e:
        logger.error(f"Error in query_db: {e}")
        logger.error(f"Query: {query}, Args: {args}")
        return None


def query_db(query, args=(), one=False):
    """Execute a query and return raw results.

    Args:
        query (str): SQL query to execute
        args (tuple): Parameters for the query
        one (bool): If True, return only the first result

    Returns:
        tuple or list of tuples: Query results
    """
    try:
        con = get_connection('default')
        with con.trans() as tr:
            cur = tr.cursor()
            cur.execute(query, args)
            cur.set_stream_blob_treshold(-1)
            r = cur.fetchone() if one else cur.fetchall()
        return r if r else None
    except Exception as e:
        logger.error(f"Error in query_db: {e}")
        logger.error(f"Query: {query}, Args: {args}")
        return None


def get_playlink():
    return clientinfo()
    """Get the playlink for a track."""


# Base64 encodiertes Image (ob Album oder Artist wird in der DB entschieden)
def get_meta_image():
    """Get base64 encoded image from the database.

    Returns:
        bytes: Base64 encoded image data
    """
    try:
        d = query_db('select m.img from getmeta m', (), True)
        if d and d[0]:
            return base64.b64encode(d[0])
        else:
            logger.warning("No image data found in getmeta")
            return b''
    except Exception as e:
        logger.error(f"Error in get_meta_image: {e}")
        return b''


# Fuer Test der JSON-Rueckgabe
def get_test(table, r, s):
    """Get test data from a table with pagination.

    Args:
        table (str): Table name
        r (str): Number of rows to return
        s (str): Number of rows to skip

    Returns:
        dict or list of dicts: Query results
    """
    try:
        query = f"select first {r} SKIP {s} * from {table}"
        return query_db_header(query, (), False)
    except Exception as e:
        logger.error(f"Error in get_test: {e}")
        return []


def play_next():
    """Request ices to play the next track via a database UDF.

    Returns:
        Any: Result of the database call
    """
    try:
        ret = query_db("select exec('/opt/firebird/UDF/r.sh') from rdb$database", (), True)
        logger.info(f"Play next result: {ret}")
        return ret
    except Exception as e:
        logger.error(f"Error in play_next: {e}")
        return None


def get_artist():
    """Get the current artist.

    Returns:
        str: Current artist name
    """
    try:
        return query_db('select ices.actartist() from actpos', (), True)
    except Exception as e:
        logger.error(f"Error in get_artist: {e}")
        return None


def get_pl():
    """Get all entries in the playlist.

    Returns:
        list: All playlist entries
    """
    try:
        return query_db('select * from showpl', ())
    except Exception as e:
        logger.error(f"Error in get_pl: {e}")
        return []


def get_admins():
    """Get list of admin users.

    Returns:
        list: List of admin users with their passwords
    """
    try:
        return query_db('select u.name,u.password from iusers u where u.iadmin>0', ())
    except Exception as e:
        logger.error(f"Error in get_admins: {e}")
        return []


def get_artists():
    """Get all known artists.

    Returns:
        list: All artist names sorted alphabetically
    """
    try:
        return query_db('select a.name from artists a order by a.name', ())
    except Exception as e:
        logger.error(f"Error in get_artists: {e}")
        return []


def get_artists_and_id():
    """Get all known artists and their id.

    Returns:
        list: All artist names sorted alphabetically
    """
    try:
        return query_db('select a.id,a.name from artists a order by a.name', ())
    except Exception as e:
        logger.error(f"Error in get_artists: {e}")
        return []


def get_albums():
    """Get all known albums with a minimum length.

    Returns:
        list: Album names sorted alphabetically
    """
    try:
        query = """
                select a.name
                from albums a
                where (select sum(t.len) from tracks t where album_pk = a.id) > 1000
                order by a.name \
                """
        return query_db(query, ())
    except Exception as e:
        logger.error(f"Error in get_albums: {e}")
        return []


def get_albums_and_id():
    """Get all known albums with a minimum length.

    Returns:
        list: Album names sorted alphabetically
    """
    try:
        query = """
                select a.id, a.name, a.ARTIST
                from albums a
                where (select sum(t.len) from tracks t where album_pk = a.id) > 1000
                order by a.name \
                """
        return query_db(query, ())
    except Exception as e:
        logger.error(f"Error in get_albums: {e}")
        return []


def get_titles():
    """Get all known titles.

    Returns:
        list: Title names sorted alphabetically
    """
    try:
        query = """
                select t.title
                from tracks t
                where t.title is not null
                  and t.title != ''
                order by t.title \
                """
        return query_db(query, ())
    except Exception as e:
        logger.error(f"Error in get_titles: {e}")
        return []


def get_titles_and_id():
    """Get all known titles.

    Returns:
        list: Title names sorted alphabetically
    """
    try:
        query = """
                select t.id, t.title, a.name
                from tracks t
                         join ARTISTS a on t.ARTIST_PK = a.id
                order by t.TITLE \
                """
        return query_db(query, ())
    except Exception as e:
        logger.error(f"Error in get_titles_and_id: {e}")
        return []


def play_titles(name):
    """Play all titles matching the given name.

    Args:
        name (str): Title name to search for
    """
    call_procedure("titleslist", name)


def play_title_by_id(id):
    """Play all tracks by the given artist.

    Args:
        id (integer): Artist id
    """
    call_procedure("titlelistbyid", id)


def play_artist(name):
    """Play all tracks by the given artist.

    Args:
        name (str): Artist name
    """

    call_procedure("artistlist", name)


def play_artist_by_id(id):
    """Play all tracks by the given artist.

    Args:
        id (integer): Artist id
    """
    call_procedure("artistlistbyid", id)


def play_album(name):
    """Play all tracks from the given album.

    Args:
        name (str): Album name
    """
    call_procedure("albumlist", name)


def play_album_by_id(id):
    """Play all tracks from the given album.

    Args:
        id (integer): Album id
    """
    call_procedure("albumlistbyid", id)


def get_title():
    """Get the currently playing title.

    Returns:
        str: Current title
    """
    try:
        return query_db('select acttitle() from actpos', (), True)
    except Exception as e:
        logger.error(f"Error in get_title: {e}")
        return None


def get_version():
    """Get the Firebird database version.

    Returns:
        str: Firebird version
    """
    try:
        con = get_connection('default')
        return con.firebird_version
    except Exception as e:
        logger.error(f"Error in get_version: {e}")
        return "Unknown"


def mopcall(payload):
    """Call Mopidy RPC API.

    Args:
        payload (dict): JSON-RPC payload

    Returns:
        dict: Response from Mopidy
    """
    try:
        # Load configuration
        config = tools.get_config()

        # Get URL from config or use default
        url = config.get('Mopidy', 'url', fallback="http://192.168.178.13:6680/mopidy/rpc")

        headers = {'content-type': 'application/json'}
        data = json.dumps(payload)

        logger.info(f"Calling Mopidy API: {url}")
        response = requests.post(url, data=data, headers=headers, timeout=5).json()
        return response
    except Exception as e:
        logger.error(f"Error in mopcall: {e}")
        return {"error": str(e)}


def get_mimage(sartist, salbum):
    """Get album image from Last.fm.

    Args:
        sartist (str): Artist name
        salbum (str): Album name

    Returns:
        Image: PIL Image object or None if not found
    """
    try:
        import pylast

        # Load configuration
        config = tools.get_config()

        # Get API key from config
        try:
            api_key = config.get('Indexer', 'LASTFM_API_KEY')
        except Exception as e:
            logger.error(f"Missing Last.fm API key in config: {e}")
            return None

        # Initialize Last.fm network
        lastfm = pylast.LastFMNetwork(api_key=api_key)

        # Get artist and album
        logger.info(f"Searching Last.fm for: {sartist} - {salbum}")
        _artist = lastfm.get_artist(sartist)
        _album = lastfm.get_album(_artist, salbum)

        # Get cover image
        try:
            cover = _album.get_cover_image(size=3)
            logger.info(f"Found cover image URL: {cover}")
        except Exception as e:
            logger.warning(f"Could not get cover image: {e}")
            cover = None

        # Download image
        if cover:
            import urllib.request

            req = urllib.request.Request(cover)
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    raw = response.read()
                    img = Image.open(BytesIO(raw))
                    logger.info(f"Successfully downloaded image for {sartist} - {salbum}")
                    return img
            except Exception as e:
                logger.error(f"Error downloading image: {e}")

        return None
    except Exception as e:
        logger.error(f"Error in get_mimage: {e}")
        return None


def get_captur():
    """Get capture information from the database.

    Returns:
        str: Capture information
    """
    try:
        s = query_db('select cinfo from getmeta m', (), True)
        return s[0] if s and s[0] else ""
    except Exception as e:
        logger.error(f"Error in get_captur: {e}")
        return ""


def get_meta(use_cache=True):
    """Get all metadata about the currently playing track.

    Args:
        use_cache (bool): Whether to use the metadata cache. Defaults to True.

    Returns:
        tuple: Metadata including time, title, artist, album, length, year, 
               percentage played, image data, image source, date, temperature,
               humidity, wind, power consumption, power production, and channel
    """
    global _meta_cache

    import time
    now = time.time()
    if use_cache and now - _meta_cache['last_update'] < META_CACHE_TIMEOUT:
        return _meta_cache['data']

    try:
        # Get the current channel (ices or tidal)
        channel = clientinfo()

        # Query based on channel
        if channel == "tidal":
            query = """
                    select substring(cast(localtime as varchar(27)) from 1 for 5),
                           m.title,
                           m.artist,
                           m.album,
                           m.len,
                           m.pyear,
                           m.percent,
                           m.img,
                           m.imgsrc,
                           dayname() || ', ' ||
                           extract(day from current_timestamp) || '.' ||
                           extract(month from current_timestamp) || '.' ||
                           extract(year from current_timestamp),
                           m.temp,
                           m.hum,
                           wind,
                           verbrauch,
                           produktion
                    from getmeta2 m \
                    """
        else:  # default to ices
            query = """
                    select substring(cast(localtime as varchar(27)) from 1 for 5),
                           m.title,
                           m.artist,
                           m.album,
                           m.len,
                           m.pyear,
                           m.percent,
                           m.img,
                           m.imgsrc,
                           dayname() || ', ' ||
                           extract(day from current_timestamp) || '.' ||
                           extract(month from current_timestamp) || '.' ||
                           extract(year from current_timestamp),
                           m.temp,
                           m.hum,
                           wind,
                           verbrauch,
                           produktion
                    from getmeta m \
                    """

        # Execute query
        mt = query_db(query, (), True)

        # Convert to list to append channel
        if mt:
            mta = list(mt)
            mta.append(channel)
            res = tuple(mta)
            _meta_cache['data'] = res
            _meta_cache['last_update'] = now
            return res
        else:
            # Return empty data if query failed
            logger.warning("No metadata found in get_meta")
            return tuple([''] * 16)

    except Exception as e:
        logger.error(f"Error in get_meta: {e}")
        # Return empty data on error
        return tuple([''] * 16)


def get_sun():
    """Get sunrise and sunset times.

    Returns:
        tuple: (sunrise time, sunset time)
    """
    try:
        return query_db('select coalesce(s.sunrise,null),coalesce(s.sunset,null) from getsun s', (), True)
    except Exception as e:
        logger.error(f"Error in get_sun: {e}")
        return None


def get_weather():
    """Get weather information.

    Returns:
        tuple: Weather data
    """
    try:
        return query_db('select weather from sysdata s where s.id= 1', (), True)
    except Exception as e:
        logger.error(f"Error in get_weather: {e}")
        return None


def get_meta_act():
    """Get metadata about the currently playing track with column headers.

    Returns:
        dict: Metadata with column names as keys
    """
    try:
        query = """
                select substring(cast(current_time as varchar(27)) from 1 for 5) as zeit,
                       m.title,
                       m.artist,
                       m.album,
                       m.len,
                       m.pyear,
                       m.percent,
                       m.imgsrc,
                       extract(day from current_timestamp) || '.' ||
                       extract(month from current_timestamp) || '.' ||
                       extract(year from current_timestamp)                      as datum
                from getmeta m \
                """
        return query_db_header(query, (), True)
    except Exception as e:
        logger.error(f"Error in get_meta_act: {e}")
        return {}


def get_users():
    """Get all users for login.

    Returns:
        list: List of users with their passwords
    """
    try:
        return query_db('select u.name,u.password from iusers u', ())
    except Exception as e:
        logger.error(f"Error in get_users: {e}")
        return []


def dec_pos():
    """Play the previous track in the playlist by decrementing the position.
    """
    call_procedure("decpos")


def artists():
    """Create a playlist with all tracks by the currently playing artist.
    """
    call_procedure("mkartistlist")


def album():
    """Create a playlist with all tracks from the currently playing album.
    """
    call_procedure("mkalbumlist")


def title():
    """Create a playlist with all versions of the currently playing title.
    """
    call_procedure("mktitlelist")


def random():
    """Return to the random playlist.
    """
    call_procedure("reset")


def bew(val):
    """Increase or decrease the rating of a track.

    Args:
        val (int): Value to add to the rating (positive or negative)
    """
    try:
        con = get_connection('default')
        with (con.trans()) as tr:
            cur = tr.cursor()
            cur.execute('execute procedure bew(?)', (val,))
            logger.info(f"Updated track rating by {val}")
    except Exception as e:
        logger.error(f"Error in bew: {e}")


def clientinfo():
    """Determine the current client channel (ices or tidal).

    Returns:
        str: Channel name ('ices' or 'tidal')
    """
    global _channel_cache
    import time
    now = time.time()
    if now - _channel_cache['last_update'] < CACHE_TIMEOUT:
        return _channel_cache['channel']

    try:
        # Default values
        channel = query_db('select name from radios r where r.id= 1', (), True)
        channel = channel[0] if channel else "ices"
        logger.info(f"Current channel: {channel}")

        # Load configuration
        config = tools.get_config()

        # Get server URL from config or use default
        server_url = config.get('Server', 'url', fallback='http://192.168.178.201:8000')
        admin_user = config.get('Server', 'admin_user', fallback='admin')
        admin_pass = config.get('Server', 'admin_pass', fallback='hackme')

        # Get external IP
        try:
            external_ip = socket.gethostbyname('motte.homelinux.net')  # logger.info(f"External IP: {external_ip}")
        except socket.gaierror as e:
            logger.warning(f"Could not resolve hostname: {e}")
            external_ip = None

        # Check ices mount
        try:
            auth = (admin_user, admin_pass)
            url = f"{server_url}/admin/listclients"

            # Check ices mount
            response = requests.get(url, params={'mount': f'/{channel}'}, auth=auth, timeout=3)
            info = response.text

            if external_ip and external_ip in info and "AvegaMediaServer" in info:
                channel = f'/{channel}'  # logger.info("Detected ices channel")

            # Check tidal mount
            response = requests.get(url, params={'mount': '/tidal'}, auth=auth, timeout=3)
            info = response.text

            if "AvegaMediaServer" in info:
                channel = "tidal"  # logger.info("Detected tidal channel")

        except requests.RequestException as e:
            logger.warning(f"Error connecting to server: {e}")

        _channel_cache['channel'] = channel
        _channel_cache['last_update'] = now
        return channel

    except Exception as e:
        logger.error(f"Error in clientinfo: {e}")
        return 'ices'  # Default to ices on error


def get_weather_data(starttime, endtime):
    """Get weather data.

    Args:
        starttime (datetime): The start time for retrieving weather data
        endtime (datetime): The end time for retrieving weather data

    Returns:
        list: List of tuples containing weather data including timestamp, temperature,
              dew point, humidity, wind speed, wind gust, rain, rain rate, pressure,
              and UV index
    """
    try:

        return query_db("select * from get_weather(?,?)", [starttime, endtime])


    except Exception as e:
        logger.error(f"Error in get_weather_data: {e}")
        return []


def get_energy(startdate, enddate=None):
    """Get energy consumption data.

    Args:
        startdate (datetime): The start date for retrieving energy data
        enddate (datetime, optional): The end date for retrieving energy data. 
                                     If None, all data from startdate is returned.

    Returns:
        list: List of tuples containing timestamp and watt-hour values
    """
    try:
        return query_db("select * from get_energy(?,?)", [startdate, enddate])

    except Exception as e:
        logger.error(f"Error in get_energy: {e}")
        return []


def get_production(startdate, enddate=None):
    """Get energy production data.

    Args:
        startdate (datetime): The start date for retrieving energy data
        enddate (datetime, optional): The end date for retrieving energy data.
                                     If None, all data from startdate is returned.

    Returns:
        list: List of tuples containing timestamp and watt-hour values
    """
    try:
        return query_db("select * from get_production(?,?)", [startdate, enddate])


    except Exception as e:
        logger.error(f"Error in get_production: {e}")
        return []


def get_image(id):
    try:
        return query_db_ro('select i.image, i.mimetype from IMAGES i where i.ID= ?', (id,))
    except Exception as e:
        logger.error(f"Error in get_image: {e}")
        return []


if __name__ == '__main__':
    # Configure logging for standalone execution
    logging.basicConfig(level=logging.INFO)

    # Test clientinfo function
    print(f"Current channel: {clientinfo()}")
    try:
        sDateNow = datetime.datetime.now()
        sDateTable = sDateNow.strftime("%Y-%m-%d")
        print(get_energy(sDateNow))
    except Exception as e:
        print(f"Error getting energy-data: {e}")
    # Test get_meta function
    try:
        meta = get_meta()
        print("Metadata:")
        print(f"Time: {meta[0]}")
        print(f"Title: {meta[1]}")
        print(f"Artist: {meta[2]}")
        print(f"Album: {meta[3]}")
        print(f"Length: {meta[4]}")
        print(f"Year: {meta[5]}")
        print(f"Percentage: {meta[6]}")
    except Exception as e:
        print(f"Error getting metadata: {e}")
