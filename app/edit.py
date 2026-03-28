from io import BytesIO
from typing import Any

from PIL import Image
from PIL.ImageFile import ImageFile

import data
import web
from web import form, Storage

# These will be initialized from main.py
render = None
session = None
debugging = False
indexer = None


def init_module(r, s, d, i):
    global render, session, debugging, indexer
    render = r
    session = s
    debugging = d
    indexer = i


def resizeimage(img: ImageFile) -> BytesIO:
    basesize = 300
    if img.width > basesize or img.height > basesize:
        img.thumbnail((basesize, basesize))
    image_io = BytesIO()
    img.save(image_io, format="PNG")
    return image_io


def imgresize(x: Storage[Any, Any]) -> BytesIO:
    img = Image.open(x.image.file)
    # Resize image if needed
    return resizeimage(img)


class edit_index:
    """Main page that shows links to artists and albums sections"""

    def GET(self):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        return render.wsgi_index(header="Album and Artist Management")


class edit_artists:
    """Display all artists with links to edit them"""

    def GET(self):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get all artists from the database
        artists_data = []
        try:
            query = "SELECT a.id, a.name, a.fk_image FROM artists a ORDER BY a.name"
            results = data.query_db_header(query)
            artists_data = results if results else []
        except Exception as e:
            print(f"Error fetching artists: {e}")

        return render.wsgi_artists(artists=artists_data, header="Artists Management")


class artist_detail:
    """Display details for a specific artist"""

    def GET(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get artist details
        try:
            query = "SELECT a.id, a.name, a.fk_image FROM artists a  where a.id = ?"
            artist = data.query_db_header(query, (artist_id,), True)

            # Get image if available
            image_data = None
            if artist and artist.get('FK_IMAGE'):
                image_data = f"/image/{artist['FK_IMAGE']}"

            # Get albums by this artist
            albums_query = "SELECT a.id, a.name, a.pyear FROM albums a WHERE a.artist = ? ORDER BY a.name"
            albums = data.query_db_header(albums_query, (artist['NAME'],))

            return render.wsgi_artist_detail(artist=artist, image=image_data, albums=albums,
                                             header=f"Artist: {artist['NAME']}")
        except Exception as e:
            print(f"Error fetching artist details: {e}")
            return "Error fetching artist details"


class artist_edit:
    """Edit artist information"""
    artist_form = form.Form(form.Textbox('name', form.notnull, description="Artist Name"),
                            form.Button('Save', type="submit"))

    def GET(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get artist details to pre-fill the form
        try:
            query = "SELECT a.id, a.name FROM artists a WHERE a.id = ?"
            artist = data.query_db_header(query, (artist_id,), True)

            if not artist:
                return "Artist not found"

            # Pre-fill the form
            form_data = self.artist_form()
            form_data.fill(name=artist['NAME'])

            return render.wsgi_artist_edit(form=form_data, artist=artist, header=f"Edit Artist: {artist['NAME']}")
        except Exception as e:
            print(f"Error fetching artist for edit: {e}")
            return "Error fetching artist details"

    def POST(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        form_data = self.artist_form()
        if not form_data.validates():
            return "Form validation failed"

        try:
            # Update artist name
            query = "UPDATE artists SET name = ? WHERE id = ?"
            data.query_db(query, (form_data.d.name, artist_id))

            # Redirect to artist detail page
            raise web.seeother(f'/edit/artist/{artist_id}')
        except Exception as e:
            print(f"Error updating artist: {e}")
            return "Error updating artist"


class artist_image:
    """Handle artist image upload and display"""

    def GET(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get artist details
        try:
            query = "SELECT a.id, a.name, a.fk_image FROM artists a WHERE a.id = ?"
            artist = data.query_db_header(query, (artist_id,), True)

            if not artist:
                return "Artist not found"

            return render.wsgi_artist_image(artist=artist, header=f"Manage Image for {artist['NAME']}")
        except Exception as e:
            print(f"Error fetching artist for image management: {e}")
            return "Error fetching artist details"

    def POST(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Handle image upload
        try:
            # Get artist details
            query = "SELECT a.id, a.name FROM artists a WHERE a.id = ?"
            artist = data.query_db_header(query, (artist_id,), True)

            if not artist:
                return "Artist not found"

            # Get uploaded file
            x = web.input(image={})
            if 'image' in x and x.image.filename:
                # Process image
                image_io = imgresize(x)

                # Create MyArtist object for the indexer
                artist_obj = indexer.MyArtist()
                artist_obj.NAME = artist['NAME']
                artist_obj.ID = artist['ID']

                # Save image using indexer
                clink = f"local://{artist['NAME']}"
                artist_obj.FK_IMAGE = indexer.saveimage(clink, image_io, 'image/png')

                # Save artist (this will update or insert image and link to artist)
                indexer.save_artist(None, artist_obj)

                # Redirect to artist detail page
                raise web.seeother(f'/edit/artist/{artist_id}')
        except Exception as e:
            print(f"Error uploading artist image: {e}")
            return f"Error uploading image: {e}"


class edit_albums:
    """Display all albums with links to edit them"""

    def GET(self):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get all albums from the database
        albums_data = []
        try:
            query = "SELECT a.id, a.name, a.artist, a.pyear, a.fk_image FROM albums a ORDER BY a.name"
            results = data.query_db_header(query)
            albums_data = results if results else []
        except Exception as e:
            print(f"Error fetching albums: {e}")

        return render.wsgi_albums(albums=albums_data, header="Albums Management")


class album_detail:
    """Display details for a specific album"""

    def GET(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get album details
        try:
            query = "SELECT a.id, a.name, a.artist, a.pyear, a.fk_image FROM albums a WHERE a.id = ?"
            album = data.query_db_header(query, (album_id,), True)

            if not album:
                return "Album not found"

            # Get image if available
            image_data = None
            if album and album.get('FK_IMAGE'):
                image_data = f"/image/{album['FK_IMAGE']}"

            # Get tracks for this album
            tracks_query = """
                           SELECT t.id, t.title, t.len, t.pyear, t.path
                           FROM tracks t
                           WHERE t.album_pk = ?
                           ORDER BY t.number, t.title \
                           """
            tracks = data.query_db_header(tracks_query, (album_id,))
            return render.wsgi_album_detail(album=album, image=image_data, tracks=tracks,
                                            header=f"Album: {album['NAME']}")
        except Exception as e:
            print(f"Error fetching album details: {e}")
            return "Error fetching album details"


class album_edit:
    """Edit album information"""
    album_form = form.Form(form.Textbox('name', form.notnull, description="Album Name"),
                           form.Button('Save', type="submit"))

    def GET(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get album details to pre-fill the form
        try:
            query = "SELECT a.id, a.name, a.artist FROM albums a WHERE a.id = ?"
            album = data.query_db_header(query, (album_id,), True)

            if not album:
                return "Album not found"

            # Pre-fill the form
            form_data = self.album_form()
            form_data.fill(name=album['NAME'])

            return render.wsgi_album_edit(form=form_data, album=album, header=f"Edit Album: {album['NAME']}")
        except Exception as e:
            print(f"Error fetching album for edit: {e}")
            return "Error fetching album details"

    def POST(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        form_data = self.album_form()
        if not form_data.validates():
            return "Form validation failed"

        try:
            # Update album name
            query = "UPDATE albums SET name = ? WHERE id = ?"
            data.query_db(query, (form_data.d.name, album_id))

            # Redirect to album detail page
            raise web.seeother(f'/edit/album/{album_id}')
        except Exception as e:
            print(f"Error updating album: {e}")
            return "Error updating album"


class album_image:
    """Handle album image upload and display"""

    def GET(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Get album details
        try:
            query = "SELECT a.id, a.name, a.artist, a.fk_image FROM albums a WHERE a.id = ?"
            album = data.query_db_header(query, (album_id,), True)

            if not album:
                return "Album not found"

            return render.wsgi_album_image(album=album, header=f"Manage Image for {album['NAME']}")
        except Exception as e:
            print(f"Error fetching album for image management: {e}")
            return "Error fetching album details"

    def POST(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        # Handle image upload
        try:
            # Get album details
            query = "SELECT a.id, a.name, a.artist FROM albums a WHERE a.id = ?"
            album = data.query_db_header(query, (album_id,), True)

            if not album:
                return "Album not found"

            # Get uploaded file
            x = web.input(image={})
            if 'image' in x and x.image.filename:
                # Process image
                img = Image.open(x.image.file)

                # Resize image if needed
                image_io = imgresize(x)
                # Create MyAlbum object for the indexer
                album_obj = indexer.MyAlbum()
                album_obj.NAME = album['NAME']
                album_obj.ARTIST = album['ARTIST']
                album_obj.ID = album['ID']

                # Save image using indexer
                clink = f"file://{album['ARTIST']}/{album['NAME']}"
                album_obj.FK_IMAGE = indexer.saveimage(clink, image_io, 'image/png')

                # Save album (this will update or insert image and link to album)
                indexer.save_album(None, album_obj)

                # Redirect to album detail page
                raise web.seeother(f'/edit/album/{album_id}')
        except Exception as e:
            print(f"Error uploading album image: {e}")
            return f"Error uploading image: {e}"


class album_image_url:
    """Download album image from a URL"""

    def POST(self, album_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        try:
            i = web.input()
            image_url = i.get('image_url')
            if not image_url:
                return "URL is required"

            # Get album details
            query = "SELECT a.name, a.artist FROM albums a WHERE a.id = ?"
            album = data.query_db_header(query, (album_id,), True)

            if not album:
                return "Album not found"

            import requests
            try:
                response = requests.get(image_url, timeout=10)
                response.raise_for_status()
                image_bytes = response.content

                # Verify it's an image
                img = Image.open(BytesIO(image_bytes))

                # Resize if needed
                if img.width > 600 or img.height > 600:
                    img.thumbnail((600, 600))
                    output = BytesIO()
                    img.save(output, format='JPEG', quality=85)
                    image_bytes = output.getvalue()

                # Save using indexer
                from indexmedia import Album
                album_obj = Album(album['NAME'], album['ARTIST'])
                album_obj.image = image_bytes
                album_obj.imgsrc = f"URL: {image_url}"
                album_obj.mimetype = 'jpeg'

                indexer.save_album(None, album_obj)

                # Redirect to album detail page
                raise web.seeother(f'/edit/album/{album_id}')
            except Exception as e:
                return f"Error downloading image from URL: {e}"
        except Exception as e:
            print(f"Error processing album image URL: {e}")
            return f"Error processing request: {e}"


class artist_image_url:
    """Download artist image from a URL"""

    def POST(self, artist_id):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('/login')
        try:
            i = web.input()
            image_url = i.get('image_url')
            if not image_url:
                return "URL is required"

            # Get artist details
            query = "SELECT a.name FROM artists a WHERE a.id = ?"
            artist = data.query_db_header(query, (artist_id,), True)

            if not artist:
                return "Artist not found"

            import requests
            headers = {'User-Agent': 'ices3 media indexer', 'From': 'fsg@users.sf.net'  # This is another valid field
                       }
            try:
                response = requests.get(image_url, headers=headers, timeout=10)
                response.raise_for_status()
                image_bytes = response.content

                # Verify it's an image
                img = Image.open(BytesIO(image_bytes))

                # Resize if needed
                outputio = resizeimage(img)

                # Save using indexer

                artist_obj = indexer.MyArtist()
                artist_obj.NAME = artist['NAME']
                artist_obj.ID = artist_id

                # Save image using indexer
                clink = f"local://{artist['NAME']}"
                artist_obj.FK_IMAGE = indexer.saveimage(clink, outputio, 'image/png')
                # Update artist with new image
                indexer.save_artist(None, artist_obj)
                # Redirect to artist detail page
                raise web.seeother(f'/edit/artist/{artist_id}')
            except Exception as e:
                return f"Error downloading image from URL: {e}"
        except Exception as e:
            print(f"Error processing artist image URL: {e}")
            return f"Error processing request: {e}"


class image_display:
    """Display an image by its ID"""

    def GET(self, image_id):
        try:
            # Get image data and mimetype
            img_result = data.get_image(image_id)

            if not img_result:
                return "Image not found"

            # Set content type header and return image data
            # img_result[0][0] is the image data, img_result[0][1] is mimetype

            web.header('Content-Type', f'{img_result[0][1]}')
            web.header('Cache-Control', 'public, max-age=604800')
            return img_result[0][0]
        except Exception as e:
            print(f"Error displaying image: {e}")
            return f"Error displaying image: {e}"
