import datetime
import hashlib
import json
import os
import re
import string
import time

import indexer.tools as tools
# Custom imports
import data
import edit
import controls
import ide_utils
from indexer import indexmedia

import web
from web import form
import fdbstore
from configparser import ConfigParser
# Configuration

debugging = ide_utils.is_running_under_ide()
web.config.debug = debugging
#print(f"Debug mode: {'enabled' if debugging else 'disabled'}")
here = os.path.dirname(__file__)

urls = ('/', 'index', '/ices', 'index', '/index', 'index', '/login', 'Login', '/logout', 'Logout', '/artists',
        'artists', '/albums', 'albums', '/titles', 'titles', '/info', 'info', '/test', 'test', '/image', 'image',
        '/playlist', 'playlist', '/plus', 'plus', '/minus', 'minus',  '/energy', 'energy',
        '/weather', 'weather', '/controls', 'controls.controls', '/edit', 'edit.edit_index', '/edit/',
        'edit.edit_index', '/edit/artists', 'edit.edit_artists', '/edit/artist/(\\d+)', 'edit.artist_detail',
        '/edit/artist/edit/(\\d+)', 'edit.artist_edit', '/edit/artist/image/(\\d+)', 'edit.artist_image',
        '/edit/artist/image/url/(\\d+)', 'edit.artist_image_url', '/edit/albums', 'edit.edit_albums',
        '/edit/album/(\\d+)', 'edit.album_detail', '/edit/album/edit/(\\d+)', 'edit.album_edit',
        '/edit/album/image/(\\d+)', 'edit.album_image', '/edit/album/image/url/(\\d+)', 'edit.album_image_url',
        '/edit/upload_image', 'edit.upload_image', '/image/(\\d+)', 'edit.image_display')

templates = os.path.join(here, 'templates')
render = web.template.render(templates, base='base')


# Application initialization
app = web.application(urls, globals(), autoreload=False)
application = app.wsgifunc()
config = tools.get_config()

icecastserver=config.get('server', 'url')
private = config.getboolean('server', 'private', fallback=False)
# Database connection
connection = tools.get_connector()
con = connection.getconnection()
store = fdbstore.FBStore(con, 'sessions')
#store = web.session.DiskStore('sessions')
# Initialize indexer for image handling
indexer = indexmedia.Indexer()

# Session configuration
web.config.session_parameters['timeout'] = 2678400
web.config.session_parameters['samesite'] = 'Strict'
web.config.session_parameters['secure'] = True
web.config.session_parameters['logged_in'] = False
web.config.session_parameters['admin'] = False
# Session initialization
if web.config.get('_session') is None:
    session = web.session.Session(app, store)
    web.config._session = session
else:
    session = web.config._session

# Initialize submodules
controls.init_module(render, web.config._session, debugging, private)
edit.init_module(render, web.config._session, debugging, indexer)


class plus():

    def GET(self):
        data.bew(1)
        raise web.seeother("index")


class minus():
    def GET(self):
        data.bew(-1)
        raise web.seeother("index")




class info:
    def GET(self):
        meta = data.get_meta_act()
        web.header('Content-Type', 'application/json')
        return json.dumps(meta)


class image:
    def GET(self):
        # Disable cache for image metadata fetch to get the very latest
        meta = data.get_meta(use_cache=False)
        if meta[7]:
            web.header('Content-Type', f'{meta[8]}')
            web.header('Cache-Control', 'public, max-age=3600')
            return meta[7]
        else:
            raise web.notfound()


class test:
    # call with eg. ices/test?table=artists&rows=10&skip=0
    def GET(self):
        dt = web.input()
        t, r, s = dt.table, dt.rows, dt.skip

        meta = data.get_test(t, r, s)
        web.header('Content-Type', 'application/json')
        return json.dumps(meta, indent=4, sort_keys=True, default=str)


class Login:
    login_form = web.form.Form(web.form.Textbox('username', web.form.notnull),
                               web.form.Password('password', web.form.notnull), web.form.Button('Login'), )
    header = "Ices Web Interface Login"

    def GET(self):
        f = self.login_form()
        return render.login(f, self.header)

    def POST(self):
        f = self.login_form
        if not f.validates():
            return render.login(f, self.header)
        allowed = data.get_users()
        username = f['username'].value
        password = f['password'].value
        # print 1/0
        if (username, password) in allowed:  # ok, in user database
            session.logged_in = True
            admin = data.get_admins()

            if (username, password) in admin:  # oh, even with admin rights
                session.admin = True
            else:
                session.admin = False
            raise web.seeother('index')
        # wrong user or password, retry ad infinitum
        return render.login(f, self.header)


class Logout:
    def GET(self):
        session.logged_in = False
        raise web.seeother('index')


class index(object):




    def mkllink(self, artist, title):
        # More efficient string handling
        combined = f"{artist} {title}"
        # Convert to ASCII directly without the bytes conversion
        slink = combined.encode('ascii', 'ignore').decode('ascii').lower()
        slink = slink.replace("the ", "").replace("&", "and")
        slink = slink.translate(str.maketrans('', '', string.punctuation))
        return slink

    def display(self):

        # global mform1
        header = "Ices Web Interface"
        # mform1 = form.Form(
        #   form.Dropdown('Play', [ 'next', 'previous','all from artist','all versions of title','complete album','random','search album','search artist']))
        #menu = self.mform1
        #sysmenu = self.sysform
        # Parentheses pattern for title cleaning
        paren_pattern = re.compile(r"\(.*?\)")

        fbversion = data.get_version()
        meta = data.get_meta()
        # Retry a few times if meta[1] is empty
        retry_count = 0
        while not meta[1] and retry_count < 10:
            time.sleep(0.1)
            meta = data.get_meta()
            retry_count += 1

        # Initialize default values
        sunrise = sunset = "0:00"
        temp = hum = wind = verbrauch = produktion = 0

        # Get weather info if admin
        if private and(debugging or session.get('admin', False)):
            winfo = data.get_weather()
            if winfo and winfo[0]:
                sun = data.get_sun()
                try:
                    if sun:
                        sunrise = datetime.time.strftime(sun[0], "%H:%M")
                        sunset = datetime.time.strftime(sun[1], "%H:%M")
                except Exception as e:
                    print(f"Error formatting sun times: {e}")

                try:
                    temp = '{:.1f}'.format(meta[10])
                    hum = meta[11]
                    wind = meta[12]
                    verbrauch = meta[13]
                    produktion = meta[14]
                    fbversion = data.get_captur()
                except Exception as e:(
                    print(f"Error in sensor data: {e}"))
        acttime = meta[0]
        actdate = meta[9]
        # Clean title more efficiently
        title = paren_pattern.sub("", meta[1]).strip()
        artist = meta[2]
        album = meta[3]
        # More efficient string formatting with f-strings
        jpclink = f"{artist}+{album}".replace(" ", "+")
        slink = self.mkllink(artist, title)
        length = tools.humanize_time(meta[4])
        year = meta[5]
        ticks = meta[6]

        # Calculate elapsed time only if ticks exist
        if ticks:
            elapsed_seconds = ticks / 100.0 * meta[4]
            elapsed = tools.humanize_time(elapsed_seconds)
        else:
            ticks = elapsed = 0

        # Initialize image dimensions
        imgblob = None

        # Process image if available
        if meta[8]:
            # Create a cache-buster based on artist and title
            # Use raw meta for cache buster to avoid issues with normalized names
            raw_id = f"{meta[2]}{meta[1]}{meta[3]}"
            unique_id = hashlib.md5(raw_id.encode('utf-8')).hexdigest()[:8]
            imgblob = f"image?{unique_id}"  # We don't need to open the image here if we only want dimensions occasionally,  # or we can keep it for layout if needed. But let's avoid it for performance.
        iwidth, iheight = 300, 300  # Default or fetch once
        isadmin = debugging or session.get('admin', False)
        showweather = private and ( debugging or session.get('admin', False))
        channel = meta[15]
        playlink = icecastserver+"/"+data.get_playlink()
        return render.index(header, artist, title, length, album, year, ticks, acttime, imgblob, fbversion, iwidth,
                            iheight, isadmin, showweather, actdate, temp, hum, wind, sunrise, sunset, slink, jpclink,
                            channel, elapsed, verbrauch, produktion,playlink,)


    # check login status and show login or main page
    def GET(self):
        if debugging or session.get('logged_in', False):
            return self.display()
        else:
            raise web.seeother('login')


class playlist:

    def datetime_handler(self, y, x):
        if isinstance(x, datetime.datetime):
            return x.isoformat()
        raise TypeError("Unknown type")

    def display(self):
        header = "Ices Web Interface Playlist"
        meta = data.get_pl()

        return render.playlist(list=meta, header=header)

    def GET(self):
        if debugging or session.get('logged_in', False):
            return self.display()
        else:
            raise web.seeother('login')


# drop down to select artist
class artists:
    arform = form.Form(form.Dropdown('Select', ['1', '2']))

    def display(self):
        header = "Select Artist"
        dt = data.get_artists_and_id()

        # Create a list of tuples (id, name) for the dropdown
        artist_options = [(str(artist_id), artist_name) for artist_id, artist_name in dt]

        # Extract just the names for the artists_data list
        artist_names = [artist_name for _, artist_name in dt]

        # Generate alphabet letters for navigation
        # Include 'All' option and letters A-Z
        letters = ['All'] + [chr(i) for i in range(65, 91)]  # A-Z

        # Create the form with the dropdown
        self.arform = form.Form(form.Dropdown('Select', artist_options, attrs={'size': '15', 'class': 'artist-select'}))

        # Pass the form, header, letters, and artist data to the template
        return render.artists(menu=self.arform, header=header, letters=letters, artists_data=artist_names)

    def GET(self):
        if debugging or session.get('logged_in', True):
            return self.display()
        else:
            raise web.seeother('login')

    def POST(self):
        # Get form data
        form_data = web.input()

        # Validate the form
        if not self.arform.validates():
            return web.seeother('index')
        else:
            # Play the selected artist by ID
            data.play_artist_by_id(int(self.arform.d.Select))
            return web.seeother('index')


# drop down list to select a specific album
class albums(object):
    alform = form.Form(form.Dropdown('Select', ['1', '2']))

    def display(self):
        header = "Select Album"
        dt = data.get_albums_and_id()

        # Create a list of tuples (id, display_text) for the dropdown
        # Display text includes album name and artist name
        album_options = [(str(album_id), f"{album_name} - {artist_name}") for album_id, album_name, artist_name in dt]

        # Extract just the display text for the albums_data list
        album_display_texts = [f"{album_name} - {artist_name}" for _, album_name, artist_name in dt]

        # Generate alphabet letters for navigation
        # Include 'All' option and letters A-Z
        letters = ['All'] + [chr(i) for i in range(65, 91)]  # A-Z

        # Create the form with the dropdown
        self.alform = form.Form(form.Dropdown('Select', album_options, attrs={'size': '15', 'class': 'album-select'}))

        # Pass the form, header, letters, and album data to the template
        return render.albums(menu=self.alform, header=header, letters=letters, albums_data=album_display_texts)

    def GET(self):
        if debugging or session.get('logged_in', False):
            return self.display()
        else:
            raise web.seeother('login')

    def POST(self):
        # Get form data
        form_data = web.input()

        # Validate the form
        if not self.alform.validates():
            return web.seeother('index')
        else:
            # Play the selected album by ID
            data.play_album_by_id(int(self.alform.d.Select))
            return web.seeother('index')


# drop down list to select a specific title
class titles(object):
    tiform = form.Form(form.Dropdown('Select', ['1', '2']))

    def display(self):
        header = "Select Title"
        dt = data.get_titles_and_id()

        # Create a list of tuples (id, display_text) for the dropdown
        # Display text includes title name and artist name
        title_options = [(str(title_id), f"{title_name} - {artist_name}") for title_id, title_name, artist_name in dt]

        # Extract just the display text for the titles_data list
        title_display_texts = [f"{title_name} - {artist_name}" for _, title_name, artist_name in dt]

        # Generate alphabet letters for navigation
        # Include 'All' option and letters A-Z
        letters = ['All'] + [chr(i) for i in range(65, 91)]  # A-Z

        # Create the form with the dropdown
        self.tiform = form.Form(form.Dropdown('Select', title_options, attrs={'size': '15', 'class': 'title-select'}))

        # Pass the form, header, letters, and title data to the template
        return render.titles(menu=self.tiform, header=header, letters=letters, titles_data=title_display_texts)

    def GET(self):
        if debugging or session.get('logged_in', False):
            return self.display()
        else:
            raise web.seeother('login')

    def POST(self):
        # Get form data
        form_data = web.input()

        # Validate the form
        if not self.tiform.validates():
            return web.seeother('index')
        else:
            # Play the selected title by ID
            data.play_title_by_id(int(self.tiform.d.Select))
            return web.seeother('index')


# Energy consumption graph page
class energy(object):
    # Create a form for date range selection
    date_form = form.Form(form.Textbox('start_date', description='Start Time'),
        form.Textbox('end_date', description='End Time'), form.Button('submit', type='submit', description='Update'))

    def GET(self):
        if debugging or session.get('logged_in', False):
            # Initialize form
            f = self.date_form()

            # Get input parameters
            user_input = web.input(start_date=None, end_date=None)

            # Get current date
            current_date = datetime.datetime.now()

            # Parse dates from input if provided
            start_date = None
            end_date = None

            try:
                if user_input.start_date:
                    # Try to parse as datetime-local format first
                    try:
                        start_date = datetime.datetime.strptime(user_input.start_date, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        # Fall back to date-only format
                        start_date = datetime.datetime.strptime(user_input.start_date, '%Y-%m-%d')
                    # Set default form value
                    f.start_date.value = user_input.start_date
                else:
                    # Default to 7 days ago
                    start_date = current_date - datetime.timedelta(hours=24)
                    f.start_date.value = start_date.strftime('%Y-%m-%dT%H:%M')

                if user_input.end_date:
                    # Try to parse as datetime-local format first
                    try:
                        end_date = datetime.datetime.strptime(user_input.end_date, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        # Fall back to date-only format
                        end_date = datetime.datetime.strptime(user_input.end_date, '%Y-%m-%d')
                    # Set default form value
                    f.end_date.value = user_input.end_date
                else:
                    # Default to current date
                    end_date = current_date
                    f.end_date.value = end_date.strftime('%Y-%m-%dT%H:%M')
            except ValueError as e:
                # Handle invalid date format
                print(f"Error parsing dates: {e}")
                start_date = current_date - datetime.timedelta(hours=24)
                end_date = current_date

            # Set end time to end of day if only date is provided
            if end_date.hour == 0 and end_date.minute == 0:
                end_date = end_date.replace(hour=23, minute=59, second=59)

            # Get energy consumption data with date range
            energy_data = data.get_energy(start_date, end_date)

            # Get energy production data with date range
            production_data = data.get_production(start_date, end_date)

            # Convert data to a format suitable for JSON
            formatted_data = []
            if energy_data:
                for row in energy_data:
                    # Format timestamp for display
                    ts = row[0].strftime("%Y-%m-%d %H:%M") if hasattr(row[0], 'strftime') else str(row[0])
                    wh = float(row[1]) if row[1] is not None else 0
                    formatted_data.append({"ts": ts, "wh": wh, "production": -1})  # Initialize production to -1

            # Add production data to the formatted data
            if production_data:
                # Create a dictionary to map timestamps to production values
                production_dict = {}
                for row in production_data:
                    ts = row[0].strftime("%Y-%m-%d %H:%M") if hasattr(row[0], 'strftime') else str(row[0])
                    power = float(row[1]) if row[1] is not None else 0
                    production_dict[ts] = power

                # Update existing entries or add new ones
                for i, item in enumerate(formatted_data):
                    if item["ts"] in production_dict:
                        formatted_data[i]["production"] = production_dict[item["ts"]]
                        # Remove from dict to track what's been processed
                        del production_dict[item["ts"]]

                # Add any remaining production data points that don't have corresponding consumption data
                for ts, power in production_dict.items():
                    formatted_data.append({"ts": ts, "wh": 0, "production": power})

                # Sort by timestamp to ensure chronological order
                formatted_data.sort(key=lambda x: x["ts"])

                # Fill missing production values using linear regression
                if formatted_data:
                    try:
                        # Convert timestamps to datetime objects for calculation
                        for i, item in enumerate(formatted_data):
                            formatted_data[i]["datetime"] = datetime.datetime.strptime(item["ts"], "%Y-%m-%d %H:%M")

                        # Find indices with valid production values
                        valid_indices = [i for i, item in enumerate(formatted_data) if item["production"] >= 0]

                        if len(valid_indices) >= 2:  # Need at least 2 points for linear regression
                            # Fill missing values
                            for i in range(len(formatted_data)):
                                if formatted_data[i]["production"] == -1:
                                    # Find nearest valid points before and after
                                    prev_idx = None
                                    next_idx = None

                                    for idx in valid_indices:
                                        if idx < i and (prev_idx is None or idx > prev_idx):
                                            prev_idx = idx
                                        if idx > i and (next_idx is None or idx < next_idx):
                                            next_idx = idx

                                    # If we have both before and after points, interpolate
                                    if prev_idx is not None and next_idx is not None:
                                        prev_point = formatted_data[prev_idx]
                                        next_point = formatted_data[next_idx]

                                        # Calculate time differences in seconds
                                        time_diff_total = (
                                                    next_point["datetime"] - prev_point["datetime"]).total_seconds()
                                        time_diff_current = (formatted_data[i]["datetime"] - prev_point[
                                            "datetime"]).total_seconds()

                                        # Linear interpolation
                                        if time_diff_total > 0:
                                            ratio = time_diff_current / time_diff_total
                                            interpolated_value = prev_point["production"] + ratio * (
                                                        next_point["production"] - prev_point["production"])
                                            formatted_data[i]["production"] = interpolated_value
                                    # If we only have points before or after, use the nearest value
                                    elif prev_idx is not None:
                                        formatted_data[i]["production"] = formatted_data[prev_idx]["production"]
                                    elif next_idx is not None:
                                        formatted_data[i]["production"] = formatted_data[next_idx]["production"]
                    except Exception as e:
                        print(f"Error during linear regression: {e}")
                    finally:
                        # Remove the datetime objects as they're not JSON serializable
                        for item in formatted_data:
                            if "datetime" in item:
                                del item["datetime"]

            # Convert to JSON for the template
            json_data = json.dumps(formatted_data)

            # Format dates for display
            display_start_date = start_date.strftime('%Y-%m-%dT%H:%M')
            display_end_date = end_date.strftime('%Y-%m-%dT%H:%M')

            return render.energy(header='Energy Consumption and Production', json_data=json_data, form=f,
                start_date=display_start_date, end_date=display_end_date)
        else:
            raise web.seeother('login')

    def POST(self):
        # Process form submission
        form_data = web.input()

        # Redirect to GET with form parameters
        raise web.seeother(f'energy?start_date={form_data.start_date}&end_date={form_data.end_date}')


# Weather data graph page
class weather(object):
    # Create a form for date range selection
    date_form = form.Form(form.Textbox('start_date', description='Start Time'),
        form.Textbox('end_date', description='End Time'), form.Button('submit', type='submit', description='Update'))

    def GET(self):
        if debugging or session.get('logged_in', False):
            # Initialize form
            f = self.date_form()

            # Get input parameters
            user_input = web.input(start_date=None, end_date=None)

            # Get current date
            current_date = datetime.datetime.now()

            # Parse dates from input if provided
            start_date = None
            end_date = None

            try:
                if user_input.start_date:
                    # Try to parse as datetime-local format first
                    try:
                        start_date = datetime.datetime.strptime(user_input.start_date, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        # Fall back to date-only format
                        start_date = datetime.datetime.strptime(user_input.start_date, '%Y-%m-%d')
                    # Set default form value
                    f.start_date.value = user_input.start_date
                else:
                    # Default to 7 days ago
                    start_date = current_date - datetime.timedelta(hours=24)
                    f.start_date.value = start_date.strftime('%Y-%m-%dT%H:%M')

                if user_input.end_date:
                    # Try to parse as datetime-local format first
                    try:
                        end_date = datetime.datetime.strptime(user_input.end_date, '%Y-%m-%dT%H:%M')
                    except ValueError:
                        # Fall back to date-only format
                        end_date = datetime.datetime.strptime(user_input.end_date, '%Y-%m-%d')
                    # Set default form value
                    f.end_date.value = user_input.end_date
                else:
                    # Default to current date
                    end_date = current_date
                    f.end_date.value = end_date.strftime('%Y-%m-%dT%H:%M')
            except ValueError as e:
                # Handle invalid date format
                print(f"Error parsing dates: {e}")
                start_date = current_date - datetime.timedelta(days=7)
                end_date = current_date

            # Set end time to end of day if only date is provided
            if end_date.hour == 0 and end_date.minute == 0:
                end_date = end_date.replace(hour=23, minute=59, second=59)

            # Get weather data with date range
            weather_data = data.get_weather_data(start_date, end_date)

            # Convert data to a format suitable for JSON
            formatted_data = []
            if weather_data:
                for row in weather_data:
                    # Format timestamp for display
                    ts = row[0].strftime("%Y-%m-%d %H:%M") if hasattr(row[0], 'strftime') else str(row[0])

                    # Extract weather data
                    temp = float(row[1]) if row[1] is not None else None
                    dew_point = float(row[2]) if row[2] is not None else None
                    humidity = float(row[3]) if row[3] is not None else None
                    wind = float(row[4]) if row[4] is not None else None
                    wind_gust = float(row[5]) if row[5] is not None else None
                    rain = float(row[6]) if row[6] is not None else None
                    rain_rate = float(row[7]) if row[7] is not None else None
                    pressure = float(row[8]) if row[8] is not None else None
                    uv_index = float(row[9]) if row[9] is not None else None

                    formatted_data.append(
                        {"ts": ts, "temp": temp, "dew_point": dew_point, "humidity": humidity, "wind": wind,
                            "wind_gust": wind_gust, "rain": rain, "rain_rate": rain_rate, "pressure": pressure,
                            "uv_index": uv_index})

            # Convert to JSON for the template
            json_data = json.dumps(formatted_data)

            # Format dates for display
            display_start_date = start_date.strftime('%Y-%m-%dT%H:%M')
            display_end_date = end_date.strftime('%Y-%m-%dT%H:%M')

            return render.weather(header='Weather Data', json_data=json_data, form=f, start_date=display_start_date,
                end_date=display_end_date)
        else:
            raise web.seeother('login')

    def POST(self):
        # Process form submission
        form_data = web.input()

        # Redirect to GET with form parameters
        raise web.seeother(f'weather?start_date={form_data.start_date}&end_date={form_data.end_date}')


if __name__ == "__main__":
    app.run()
