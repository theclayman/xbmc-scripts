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
    args = parseargs()

    #outfilename = getoutfilename(args.xmlfilename)
    #if(os.path.exists(outfilename)):
    #    print("Ausgabedatei existiert bereits und wird nicht ueberschrieben. Bitte Eingabedatei anders benennen.")
    #    sys.exit(1)

    movies1 = parsexml(args.xmlfilename1)
    movies2 = parsexml(args.xmlfilename2)

    excludelist = None
    if(args.excludelist != None):
        excludelist = readexcludelist(args.excludelist)
        # alle Filme auf der Ausschlussliste nicht berücksichtigen

    difflist = comparemovies(movies1, movies2, excludelist)
    exportdifflist(difflist)

    #exportmovielist(movies, outfilename)

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


def comparemovies(movies1, movies2, excludelist=None):
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

def findMovieWithTitleAndYear(movie, movielist):
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


def parseargs():
    parser = argparse.ArgumentParser("Export-Skript für XBMC-Bibliothek")
    parser.add_argument("-x1", "--xmlfile1", help="erste Filmliste im XML-Format", dest="xmlfilename1", required=True)
    parser.add_argument("-x2", "--xmlfile2", help="zweite Filmliste im XML-Format", dest="xmlfilename2", required=True)
    parser.add_argument("-e", "--excludelist", help="Liste mit auszuschliessenden Filmtiteln", dest="excludelist")
    args = parser.parse_args()
    return args


if __name__ == '__main__':
    #sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
    main()
    #unittest.main()

