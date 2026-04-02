import os
import signal
from subprocess import call

import psutil

import data
import indexer.tools as tools
import web
from web import form

# These will be initialized from main.py
render = None
session = None
debugging = False
private = False


def init_module(r, s, d, p):
    global render, session, debugging, private
    render = r
    session = s
    debugging = d
    private = p


class controls(object):
    mform1 = form.Form(

        form.Dropdown('Action',
                      [ 'next', 'previous', 'Remove', 'all from artist', 'all versions of title', 'complete album',
                       'random', 'search album', 'search artist', 'search title'], value='next'),
        # form.Button('Remove', value='minus'),
    )
    sysform = form.Form(form.Dropdown('System', ['jetzt laden', 'automatisch laden', 'Klimatisierung starten']), )

    # decrement playlist pointer, then tell ices
    @staticmethod
    def sendprevious():
        data.dec_pos()  # sendnext()

    @staticmethod
    def sendnext():
        for proc in psutil.process_iter():
            if proc.name() == 'ices' :
                os.kill(proc.pid, signal.SIGUSR1)



    # create playlist with all titles from actual album, then tell ices
    @staticmethod
    def sendalbum():
        data.album()  # sendnext()

    # create playlist with all versions of actual title, then tell ices
    @staticmethod
    def sendtitle():
        data.title()  # sendnext()

    # create playlist with all tracks of current artist, then tell ices
    @staticmethod
    def sendartist():
        data.artists()  # sendnext()

    @staticmethod
    def remove():
        data.bew(-5)

    # return to randomized playlist, tell ices
    @staticmethod
    def sendrandom():
        data.random()  # sendnext()

    @staticmethod
    def lademodusauto():
        call(["./static/script/auto.sh"])

    @staticmethod
    def startklima():
        call(["./static/script/klima.sh"])

    @staticmethod
    def lademodusmanuell():
        call(["./static/script/manuell.sh"])

    def display(self):
        header = "Ices Web Interface Controls"
        # We need to access mform1 and sysform from index class
        menu = self.mform1
        if private:
            sysmenu = self.sysform
        else:
            sysmenu = None
        isadmin = debugging or session.get('admin', False)
        return render.controls(menu, sysmenu, header, isadmin)

    def GET(self):
        if debugging or session.get('admin', False):
            return self.display()
        else:
            raise web.seeother('login')

    def POST(self):
        if not (debugging or session.get('admin', False)):
            raise web.seeother('login')
        target = 'index'
        i = web.input()
        try:

            if 'Action' in i:
                menu = self.mform1
                if not menu.validates():
                    return self.display()
                if debugging or session.get('admin', False):
                    for case in tools.switch(menu.d.Action):
                        if case('Remove'):
                            self.remove()
                            self.sendnext()
                            break
                        if case('next'):
                            self.sendnext()
                            break
                        if case('previous'):
                            self.sendprevious()
                            break
                        if case('all from artist'):
                            self.sendartist()
                            break
                        if case('all versions of title'):
                            self.sendtitle()
                            break
                        if case('complete album'):
                            self.sendalbum()
                            break
                        if case('random'):
                            self.sendrandom()
                            break
                        if case('search artist'):
                            target='artists'
                            break

                        if case('search album'):
                            target='albums'
                            break

                        if case('search title'):
                            target='titles'
                            break


            elif 'System' in i:
                sysmenu = self.sysform
                if not sysmenu.validates():
                    return self.display()
                if debugging or session.get('admin', False):
                    for case in tools.switch(sysmenu.d.System):
                        if case('jetzt laden'):
                            self.lademodusmanuell()
                            break
                        if case('automatisch laden'):
                            self.lademodusauto()
                            break
                        if case('Klimatisierung starten'):
                            self.startklima()
                            break
        except Exception as e:
            if not f"{e}"=="303 See Other":
                print(f"Error in controls POST: {e}")
                target='index'
        finally:
            web.seeother(target)