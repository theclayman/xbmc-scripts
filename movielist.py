# -*- encoding: utf-8 -*-
import argparse
import xml.etree.ElementTree as ET
import codecs
import os
import locale
import sys
import csv
import itertools
import unittest
import re
import pdb

# Ideen:
# - in Dateinamen das Jahr ergänzen, das in der XML-Datei steht.
#   Dabei sollte Nutzer entscheiden, ob die jeweilige Datei umbenannt wird
# - Ausschlussliste aus Datei laden: wenn ich meine Liste mit einer anderen
#   vergleiche um zu prüfen, welche Filme mir noch fehlen, möchte ich Filme
#   ausschließen, die ich schon mal gelöscht habe, weil sie mir nicht gefallen
# - Vergleich zweier Listen implementieren, alternative ist Diff-Programm

class MyTests(unittest.TestCase):
    def test_stringToMovie_WithValidString_ReturnsMovie(self):
        string = "Inception (2012)"
        movie = stringToMovie(string)
        self.assertEqual(movie.Title, "Inception")
        self.assertEqual(movie.Year, "2012")

def main():
    parser = argparse.ArgumentParser("Export-Skript für XBMC-Bibliothek")
    subparsers = parser.add_subparsers(help="sub-command help")

    parser_compare = subparsers.add_parser("compare", help="Zwei aus XMBC exportierte XML-Dateien vergleichen")
    parser_compare.add_argument("-x1", "--xmlfile1", help="erste Filmliste im XML-Format", required=True)
    parser_compare.add_argument("-x2", "--xmlfile2", help="zweite Filmliste im XML-Format", required=True)
    parser_compare.add_argument("-e", "--excludelist", help="Liste mit auszuschliessenden Filmtiteln", dest="excludelist")
    parser_compare.set_defaults(func=compareXmlMovieLists)

    parser_rename = subparsers.add_parser("rename", help="Filmdateien anhand einer aus XMBC exportierten XML-Datei umbenennen.")
    parser_rename.add_argument("-x", "--xmlfile", help="Aus XBMC exportierte Filmliste (XML)", required=True)
    parser_rename.add_argument("-b", "--basepath", help="Das Verzeichnis, in dem die Filmdateien zu finden sind.", required=True)
    parser_rename.set_defaults(func=renameMovieFiles)
    args = parser.parse_args()
    args.func(args)


def compareXmlMovieLists(args):
    movies1 = parsexml(args.xmlfilename1)
    movies2 = parsexml(args.xmlfilename2)

    excludelist = []
    if(args.excludelist != None):
        # alle Filme auf der Ausschlussliste nicht berücksichtigen
        excludelist = readexcludelist(args.excludelist)


    difflist = comparemovies(movies1, movies2, excludelist)
    exportdifflist(difflist)

    #exportmovielist(movies, outfilename)

def renameMovieFiles(args):
    if(not os.path.exists(args.basepath)):
        print("Das Basisverzeichnis existiert nicht: %s" % args.basepath)
        sys.exit(1)


    movielist = parsexml(args.xmlfile)
    for movie in movielist:
        # prüfe ob Datei im Zielpfad überhaupt existiert. Hierzu muss man den
        # Dateinamen des Films im angegebenen Basispfad suchen, denn XMBC greift
        # in den meisten Fällen über einen ganz anderen Pfad (bspw. eine Netzwerkfreigabe)
        # auf die Filmdateien zu als dieses Skript.

        path, filenameWithExtension = os.path.split(movie.FilePath)
        filename, extension = os.path.splitext(filenameWithExtension)

        movieLocalPath = os.path.join(args.basepath, filenameWithExtension)
        if(not os.path.exists(movieLocalPath)):
            print("Filmdatei existiert nicht: " + movieLocalPath)
            continue

        # enthält Dateiname die Jahreszahl des Films in runden Klammern?
        # Beispiel: "Shutter Island (2010).mkv"
        movieFromFilename = stringToMovie(filename)

        # Jahr im Dateinamen anders als in Filmdatenbank
        if(movieFromFilename.Year != movie.Year):
            newFilename = "%s (%s)%s" % (filename, movie.Year, extension)
            newFilePath = os.path.join(args.basepath, newFilename)
            question = "Soll die Datei \n\t%s\nin\t%s\n umbenannt werden?" % \
                (movie.Filename, newFilePath)
            answer = query_yes_no_cancel(question)
            if(answer == True):
                try:
                    os.rename(movieLocalPath, newFilePath)
                except OSError as err:
                    "Konnte Datei nicht umbenennen. Fehlermeldung: " + err


def query_yes_no_cancel(question):
    valid = {"yes":True,
             "y":True,
             "j":True,
             "no":False,
             "nein":False,
             "n":False,
             "c":None,
             "cancel":None,
             }
    prompt = "y/j/n/c (yes/ja/no/nein/cancel/)"

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Ungueltige Eingabe.")


def readexcludelist(filename):
    movielist = []
    with codecs.open(filename, "r", encoding="UTF-8") as infile:
        for line in infile:
            movie = stringToMovie(line)
            movielist.append(movie)

    return movielist

def stringToMovie(line):
    """Extrahiert aus einer Zeichenkette im Format Filmtitel (Jahr) den Titel und
das Jahr und gibt ein entsprechendes Objekt vom Typ Movie zurück."""
    # zuerst nach Jahr in Klammern suchen
    yearPattern = re.compile("\(\d{4,4}\)")
    yearMatch = yearPattern.search(line)
    year = None
    if(yearMatch != None):
        year = yearMatch.group()[1:-1] # Klammern entfernen
        # das Jahr inkl. Klammern entfernen
        line = re.sub(yearPattern, "", line)

    # Filmtitel extrahieren, Leerzeichen entfernen
    title = line.strip()
    if(title == "" and year == None):
        return None

    movie = Movie()
    movie.Title = title
    movie.Year = year
    return movie

def exportdifflist(difflist):
    # bevor itertools.groupby angewendet wird, muss die Liste sortiert werden,
    # weil groupby immer dann eine neue Gruppe beginnt, wenn sich der definierte
    # Schlüssel vom einen zum anderen ändert (im Gegensatz zu SQL group by)
    difflist = sorted(difflist, key = lambda x: x.difftype)
    with codecs.open("difflist.txt", "w", encoding = "UTF-8") as outfile:
        for group, movielist in itertools.groupby(difflist, lambda x: x.difftype):
            outfile.write("%s\n" % group)
            for entry in sorted(movielist, key = lambda x: x.movie.Title):
                outfile.write("  %s (%s)\n" % (entry.movie.Title, entry.movie.Year))


def comparemovies(movies1, movies2, excludelist=[]):
    results = []

    for movie in movies2:
        # steht Film in Ausschlussliste
        foundmovie = findMovieWithTitleAndYear(movie, excludelist)
        if(len(foundmovie) > 0):
            print("Lasse film aus: " + movie.Title)
            continue

        # habe ich den Film schon?
        findresult = findmovie(movie, movies1)
        if(findresult != None):
            results.append(findresult)

    return results

def findMovieWithTitleAndYear(movie, movielist = []):
    foundmovies = list(filter(lambda m: (movie.Title == m.Title) and (movie.Year == m.Year), movielist))
    return foundmovies

def findmovie(movie, movielist):
    foundmovies = findMovieWithTitleAndYear(movie, movielist)
    if(len(foundmovies) == 0):
        # Film wurde in der Liste nicht gefunden, er fehlt also in meiner Sammlung
        return FindResult("NEW", movie)
    elif(len(foundmovies) == 1):
        # Film ist in meiner Sammlung schon vorhanden, aber jetzt prüft man,
        # ob er in der anderen Sammlung in besserer Qualität vorhanden ist
        newmovie = foundmovies[0]
        if( (movie.ResolutionWidth * movie.ResolutionHeight) >
            (newmovie.ResolutionWidth * newmovie.ResolutionHeight)):
                return FindResult("RESOLUTION", movie)
    else:
        print("Film ist in Sammlung doppelt vorhanden: %s" % movie)
        return FindResult("DUPLICATE", movie)

class FindResult:
    def __init__(self, difftype, movie):
        self.difftype = difftype
        self.movie = movie

    def __str__(self):
        return "%s %s" % (self.difftype, self.movie)

def getoutfilename(xmlfilename):
    filename = os.path.basename(xmlfilename)
    return filename + "_export.csv"

def exportmovielist(movies, outfilename):
    with codecs.open(outfilename, "w", encoding = "UTF-8") as outfile:
        # mehrfaches sortieren nach verschiedenen Kriterien: https://wiki.python.org/moin/HowTo/Sorting

        csvwriter = csv.writer(outfile, delimiter='\t', quoting=csv.QUOTE_NONE)
        for movie in sorted(movies, key=lambda x: x.Title):
            #outfile.write(str(movie) + "\n")
            csvwriter.writerow([movie.Title, movie.OriginalTitle, movie.Year, movie.resolutionSymbol()])


def parsexml(xmlfile):
    try:
        xml = ET.parse(xmlfile)
    except IOError:
        print("Eingabedatei konnte nicht geöffnet werden.")
        sys.exit(1)

    movies = []
    for moviexml in xml.iter('movie'):
        movie = Movie()

        origtitle = moviexml.find("originaltitle")
        if(origtitle == None):
            sorttitle = moviexml.find("sorttitle")
            print("Kein <originaltitle> vorhanden, verwende <sorttitle>: %s" % sorttitle.text)

            #print(ET.tostring(moviexml))
        else:
            movie.OriginalTitle = moviexml.find("originaltitle").text
            movie.Title = moviexml.find("title").text

        movie.Year = moviexml.find("year").text

        filename = os.path.basename(moviexml.find("filenameandpath").text)
        movie.Filename = filename
        movie.FilePath = moviexml.find("filenameandpath").text

        try:
            video = moviexml.find("fileinfo").find("streamdetails").find("video")
            width = int(video.find("width").text)
            height = int(video.find("height").text)
            movie.ResolutionHeight = height
            movie.ResolutionWidth = width
        except AttributeError:
            #print("Could not get resolution for movie: %s", str(movie.Title))
            pass

        movies.append(movie)


    return movies

class Movie:
    def __init__(self):
        self.Title = ""
        self.OriginalTitle = ""
        self.Year = ""
        self.Filename = ""
        self.FilePath = ""
        self.ResolutionWidth = 0
        self.ResolutionHeight = 0

    def __str__(self):
        return "%s (%s) [%s]  %sx%s %s" % (self.Title, self.OriginalTitle, self.Year, self.ResolutionWidth, self.ResolutionHeight, self.resolutionSymbol())

    def resolutionSymbol(self):
        """Liefert in Abhängigkeit der Auflösung eine Abkürzung hierfür zurück: FullHD, HD, SD, ?"""
        if(self.ResolutionHeight == 0 or self.ResolutionWidth == 0):
            return "?"
        if (self.ResolutionWidth >= 1920 and self.ResolutionHeight >= 1080):
            return "FullHD"
        if(self.ResolutionWidth >=  1280 and self.ResolutionHeight >= 720):
            return "HD"
        #return "%sx%s" % (self.ResolutionWidth, self.ResolutionHeight)
        return "SD"

if __name__ == '__main__':
    #sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
    main()
    #unittest.main()

