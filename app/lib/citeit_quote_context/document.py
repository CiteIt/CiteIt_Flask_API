# Copyright (C) 2015-2020 Tim Langeman and contributors
# <see AUTHORS.txt file>
#
# This library is part of the CiteIt project:
# http://www.citeit.net/

# The code for this server library is released under the MIT License:
# http://www.opensource.org/licenses/mit-license

from lib.citeit_quote_context.canonical_url import Canonical_URL
from lib.citeit_quote_context.content_type import Content_Type
from lib.citeit_quote_context.canonical_url import url_without_protocol

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

import urllib
from urllib.parse import urlparse
from urllib.parse import parse_qs

from datetime import datetime
from langdetect import detect    # https://www.geeksforgeeks.org/detect-an-unknown-language-using-python/
from functools import lru_cache
import ftfy                      # Fix bad unicode:  http://ftfy.readthedocs.io/
import re
import timeit
import settings
import tldextract

import youtube_dl

from bs4 import BeautifulSoup  # convert html > text



FOLDER_SEPARATOR = "%2"
PDF_PREFIX = "../downloads/"


__author__ = 'Tim Langeman'
__email__ = "timlangeman@gmail.com"
__copyright__ = "Copyright (C) 2015-2020 Tim Langeman"
__license__ = "MIT"
__version__ = "0.4"

HEADERS = {
   'user-agent': 'Mozilla / 5.0(Windows NT 6.1;'
   ' WOW64; rv: 54.0) Gecko/20100101 Firefox/71.0'
}


class Document:
    """ Look up url and compute plain-text version of document
        Use caching to prevent repeated re-querying

        url = 'https://www.openpolitics.com/articles/ted-nelson-philosophy-of-hypertext.html'
        doc = Document(url)
        page_text = doc.text()
    """

    def __init__(self, url	):
        self.url = url  # user supplied URL, may be different from canonical
        self.num_downloads = 0  # count number of times the source is downloaded
        self.request_start = datetime.now()  # time how long request takes
        self.request_stop = None  # Datetime of last download

        self.unicode = ''
        self.content = ''      # raw (binary)
        self.encoding = ''     # character encoding of document, returned by requests library
        self.error = ''
        self.language = ''
        self.content_type = ''

        self.request_dict = {
            'text': '',        # unicode
            'unicode': '',
            'content': '',     # raw
            'encoding': '',
            'error':  '',
            'language': '',
            'content_type': ''
        }

    def url(self):
        return self.url

    @lru_cache(maxsize=500)
    def download_resource(self):

        # Was this file already downloaded?
        if (len(self.content_type) >= 1) :
            print("ALREADY DOWNLOADED.")
            return self.request_dict

        try:
            self.increment_num_downloads()
            error = ''
            url = self.url

            # Use a User Agent to simulate what a Firefox user would see
            session = requests.Session()
            retry = Retry(connect=5, backoff_factor=0.5)
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            try:
                r = session.get(url, headers=HEADERS, verify=False)
            except requests.exceptions.ConnectionError:
                # r.status_code = "Connection refused"
                return {
                    'text': '',              # unicode
                    'unicode': url,
                    'content': url,   # raw
                    'encoding': '',
                    'error': "Connection refused",
                    'language': '',
                    'content_type': ''
                }

            print('Downloaded ' + url )
            self.request_stop = datetime.now()
            print("Encoding: %s" % r.encoding )
            print("num downloads: " + str(self.num_downloads))

            text = r.text
            self.unicode = r.text
            self.content = r.content

            self.encoding = r.encoding
            self.error = error
            self.language = detect(r.text) # https://www.geeksforgeeks.org/detect-an-unknown-language-using-python/
            self.content_type = r.headers['Content-Type']

            print('Content-Type: ' + self.content_type)
            print('Language:     ' + self.language)
            print('Length: ' + str(len(self.content)))
            print("Attempting to save ..  ")

            ####### Archive a Copy of the Original File ########
            doc_type = self.doc_type()
            print("DocType::: " + doc_type)

            if (settings.SAVE_DOWNLOADS_TO_FILE):
                if (self.content_type.startswith('text')):
                    open(self.filename_original(), 'w').write(r.text)   # text or html
                else:
                    open(self.filename_original(), 'wb').write(self.content)  # binary

            print("Saved original: " + self.filename_original() )
            print('Content-Type: ' + self.content_type)
            print('Language:     ' + self.language)
            print('Length: ' + str(len(r.content)))


        except requests.HTTPError:
            self.request_stop = datetime.now()

            """ TODO: Add better error tracking """
            error = "document: HTTPError"

        self.request_dict = {
            'text': text,              # unicode
            'unicode': self.unicode,
            'content': self.content,   # raw
            'encoding': self.encoding,
            'error': self.error,
            'language': self.language,
            'content_type': self.content_type
        }

        return self.request_dict

    def download_dict(self):
        return self.request_dict


    @lru_cache(maxsize=20)
    def download(self, convert_to_unicode=False):
        """
            Download the data and update tracking metrics
        """
        # return utf-8 content
        return self.download_resource()['text']  # default to blank string


    @lru_cache(maxsize=500)
    def text(self):
        """ Create a text-only version of a document
            In the future, this method would handle other document formats
            such as PDF and Word doc

            Right now, only the HTML conversion is implemented
            I've made comments about possible implementations,
            if you're intested in implementing one of the other methods,

            Idea: https://github.com/skylander86/lambda-text-extractor
        """
        pdf_prefix = "../downloads/"
        doc_type = self.doc_type()


        if (doc_type == 'html'):
            print("HTML text()")

            # Check Media Provider for transcript: Youtube Video
            if (len(self.media_provider()) > 0):
                supplemental_text = self.supplemental_text()

            soup = BeautifulSoup(self.html(), "html.parser")
            invisible_tags = ['style', 'script', '[document]', 'head', 'title']
            for elem in soup.findAll(invisible_tags):
                elem.extract()  # hide javascript, css, etc
            text = soup.get_text()

            text = ftfy.fix_text(text)  # fix unicode problems
            text = convert_quotes_to_straight(text)
            text = normalize_whitespace(text)

            html_text = text + '\n\n' + self.supplemental_text()
            html_text = html_text.strip()

            if (settings.SAVE_DOWNLOADS_TO_FILE):
                open(self.filename_text(), 'w').write(html_text)

            return html_text

        elif (doc_type == 'pdf'):
            # example: https://demo.citeit.net/2020/06/30/well-behaved-women-seldom-make-history-original-pdf/
            # quoted source: https://dash.harvard.edu/bitstream/handle/1/14123819/Vertuous%20Women%20Found.pdf

            try:
                import pdftotext  # convert pdf > text without using ocr
            except ImportError:
                return "Unable to process digital PDF. Pdftotext library not installed."

            print("Start PDF processing ..")
            filename_original = self.filename_original()
            filename_text = self.filename_text()

            print("Filename original: " + filename_original)
            print("Filename:    text: " + filename_text)

            if (settings.SAVE_DOWNLOADS_TO_FILE):
                with open(filename_original, 'rb') as f:
                    pdf = pdftotext.PDF(f)

            """
            // Credit: https://pypi.org/project/pdftotext/
            
            # How many pages?
            print(len(pdf))

            # Iterate over all the pages
            for page in pdf:
                print(page)

            # Read some individual pages
            print(pdf[0])
            print(pdf[1])
            """

            pdf_text = "\n\n".join(pdf)  # Combine text into single string
            pdf_text = pdf_text.strip()

            if (settings.SAVE_DOWNLOADS_TO_FILE):
                # Digital PDF with digitally extractable text: https://dash.harvard.edu/bitstream/handle/1/14123819/Vertuous%20Women%20Found.pdf
                if (len(pdf_text) > 0):
                    print("Saving digital pdf text version to: " + filename_text)
                    open(filename_text, 'w').write(pdf_text)

                    return pdf_text

                # OCR: Generate text version from scanned doc using OCR (more CPU intensive)
                else:  # example: https://faculty.washington.edu/rsoder/EDLPS579/DostoevskyGrandInquisitor.pdf
                    start_time = timeit.default_timer()

                    try:
                        from pdf2image import convert_from_path
                        import pytesseract  # ocr library for python
                        import glob
                    except ImportError:
                        return "Unable to run OCR to generate PDF from scanned image.  Pdf2impage, Pytesseract not installed for Docker"

                    pdf_output = ''
                    language = 'eng'

                    pdfs = glob.glob(filename_original)
                    print("PDF globs")

                    for original_pdf_path in pdfs:
                        pages = convert_from_path(filename_original, 500)
                        print("PDFs converted.  Now enumerating ..")

                        for pageNum, imgBlob in enumerate(pages):

                            print("Page: " + str(pageNum))

                            output_filename_page = pdf_prefix + 'pdf/' + urllib.parse.quote_plus(self.canonical_url_without_protocol()) + ".txt" + '@@-page-' + str(
                                pageNum).zfill(4) + '.txt'

                            output_filename_complete = pdf_prefix + 'pdf/' + urllib.parse.quote_plus(self.canonical_url_without_protocol()) + ".txt"

                            # Use OCR to convert image > text
                            text = pytesseract.image_to_string(imgBlob, language)
                            pdf_output = pdf_output + ' ' + text

                            # Write individual file:
                            if (settings.SAVE_DOWNLOADS_TO_FILE):
                                print(output_filename_page)
                                with open(output_filename_page, 'w') as the_file:
                                    the_file.write(text)

                    if (settings.SAVE_DOWNLOADS_TO_FILE):
                        # Write Entire Text to file
                        with open(output_filename_complete, 'w') as the_file:
                            the_file.write(pdf_output)

            # takes roughly 90 minutes (16 seconds per page)
            print("The time difference is :",
                  timeit.default_timer() - start_time)

            if ('â€™' in pdf_output) or ('â€' in pdf_output) or ('â€œ' in pdf_output):
                pdf_output = pdf_output.encode("Windows-1252").force_encoding("UTF-8")

            return pdf_output

        elif (doc_type == 'json'):
            print("SUPPLEMENTAL TEXT()")
            return self.supplemental_text()

        elif (doc_type == 'txt'):
            return self.raw()

        elif (doc_type == 'rtf'):
            return "RTF support not yet implemented.  To implement it see: http://www.gnu.org/software/unrtf/"

        elif (doc_type == 'epub'):
            return "EPub support not yet implemented.  To implement it see: https://github.com/aerkalov/ebooklib"

        elif (doc_type == 'doc'):
            return "Doc support not yet implemented. To implement it see: http://www.winfield.demon.nl/"

        elif (doc_type == 'docx'):
            return "Doc support not yet implemented. To implement it see: https://github.com/ankushshah89/python-docx2txt"

        elif (doc_type == 'pptx'):
            return "Powerpoint support not yet implemented.  To implement it see:  https://python-pptx.readthedocs.org/en/latest/"

        elif (doc_type == 'ps'):
            return "Doc support not yet implemented.  To implement it see: http://www.winfield.demon.nl/"

        elif (doc_type == 'audio/mpeg'):
            return "MP3 support not yet implemented.  To implement it see: https://pypi.org/project/SpeechRecognition/"

        elif (doc_type == 'audio/ogg'):
            return "OGG support not yet implemented.  To implement it see: https://pypi.org/project/SpeechRecognition/"

        elif (doc_type == 'video/ogg'):
            return "OGG support not yet implemented.  To implement it see: https://pypi.org/project/SpeechRecognition/"

        elif (doc_type == 'wav'):
            return "WAV support not yet implemented.  To implement it see: https://pypi.org/project/SpeechRecognition/"

        elif (doc_type == 'aac'):
            return "AAC support not yet implemented.  To implement it see: https://pypi.org/project/SpeechRecognition/"

        elif (doc_type == 'jpg'):
            return "JPG support not yet implemented.  To implement it see: https://github.com/tesseract-ocr/"

        elif (doc_type == 'png'):
            return "PNG support not yet implemented.  To implement it see: https://github.com/tesseract-ocr/"

        elif (doc_type == 'tiff'):
            return "TIFF support not yet implemented.  To implement it see: https://github.com/tesseract-ocr/"

        elif (doc_type == 'gif'):
            return "GIF support not yet implemented.  To implement it see: https://github.com/tesseract-ocr/"

        elif (doc_type == 'webp'):
            return "WebP support not yet implemented. Does Tesseract support it?  https://github.com/tesseract-ocr/"

        elif (doc_type == 'xls'):
            return "XLS support not yet implemented.  To implement it see: https://pypi.python.org/pypi/xlrd"

        elif (doc_type == 'xlsx'):
            return "XLSX support not yet implemented.  To implement it see: https://pypi.python.org/pypi/xlrd"

        elif (doc_type == 'json'):
            print("JSON DOC TYPE")
            text = ''
            if (len(self.media_provider()) > 0):
                text = self.supplemental_text()

            return text

        else:
            return 'error: no doc_type: ' + doc_type

    def content_type_lookup(self):

        if (len(self.content_type) > 0):
            return self.content_type
        else:
            return self.download_resource()['content_type']


    @lru_cache(maxsize=500)
    def doc_type(self):
        # Distinguish between html, text, .doc, ppt, and pdf
        content_type = self.content_type_lookup()
        doc_type = Content_Type.doc_type(content_type)
        return doc_type

    def media_provider(self):

        ext = tldextract.extract(self.url)

        # YouTube
        if (ext.domain == 'youtube' and ext.suffix == 'com'):
            return 'youtube'

        elif (ext.domain == 'youtu' and ext.suffix == 'be'):
            return 'youtube'

        # Vimeo
        elif (ext.domain == 'vimeo' and ext.suffix == 'com'):
            return 'vimeo'

        # Soundcloud
        elif (ext.domain == 'soundcloud' and ext.suffix == 'com'):
            return 'soundcloud'

        # OYEZ : Supereme Court Transcripts
        elif (ext.domain == 'oyez' and ext.suffix == 'org'):
            return 'oyez.org'

        else:
            return ''


    def supplemental_text(self):

        url = self.url
        supplemental_text = ''

        media_provider = self.media_provider()

        if (media_provider == 'youtube'):
            supplemental_text = youtube_transcript(url)

        elif (media_provider == 'vimeo'):
            supplemental_text = "Vimeo transcripts not yet implemented. (See document.supplemental_text() )"

        elif (media_provider == 'oyez.org'):
            supplemental_text = oyez_transcript(url)

        return supplemental_text

    @lru_cache(maxsize=20)
    def raw(self, convert_to_unicode=True):
        """
            This method returns the raw, unprocessed data, but
            it is cached for performance reasons, using @lru_cache
        """
        raw = self.download(convert_to_unicode=convert_to_unicode)
        if raw:
            return raw
        else:
            return ''

    @lru_cache(maxsize=500)
    def html(self):
        """ Get html code, if doc_type = 'html' """
        html = ""
        print('unicode' + self.download_resource()['unicode'])

        if self.doc_type() == 'html':
            #html = self.download_resource()['unicode']   #self.raw()
            html = self.unicode

        return html

    @lru_cache(maxsize=20)
    def canonical_url(self):
        """ Web pages may be served from multiple URLs.
            The canonical url is the preferred, permanent URL.
            Use BeautifulSoup to process html and find <link> or <meta> tags.

            Credit: http://pydoc.net/Python/pageinfo/0.40/pageinfo.pageinfo/
        """

        html = self.html()

        return  Canonical_URL(html, url=self.url).canonical_url()

    @lru_cache(maxsize=500)
    def canonical_url_without_protocol(self):
        return url_without_protocol(self.canonical_url())

    @lru_cache(maxsize=500)
    def citeit_url(self):
        """ Use the canonical_url, if it exists.
            Otherwise, use the user-supplied url.
        """

        citeit_url = Canonical_URL(self.html()).citeit_url()

        if citeit_url:
            return citeit_url
        else:
            return self.url_without_protocol()

    def url_without_protocol(self):
        return Canonical_URL(self.url).url_without_protocol()


    @lru_cache(maxsize=500)
    def filename_original(self):
        canonical_path = urllib.parse.quote_plus(self.canonical_url_without_protocol())

        # Example '../downloads/html/avalon.law.yale.edu/19th_century/jeffauto.asp'#
        original_file_path = PDF_PREFIX + self.doc_type() + '/' + canonical_path

        return original_file_path

    def filename_text(self):
        return self.filename_original() + '.txt'


    @lru_cache(maxsize=500)
    def data(self, verbose_view=False):
        """ Dictionary of data associated with URL """
        data = {}
        data['url'] = self.url
        data['canonical_url'] = self.canonical_url()
        data['citeit_url'] = self.citeit_url()
        data['doc_type'] = self.doc_type()
        data['language'] = self.language()

        data['encoding'] = self.encoding()
        data['request_start'] = self.request_start
        data['request_stop'] = self.request_stop
        data['elapsed_time'] = str(self.elapsed_time())
        data['text'] = self.text()
        data['raw'] = self.raw()

        if (verbose_view):
            data['raw_original_encoding'] = self.raw(convert_to_unicode=False)
            data['num_downloads'] = self.num_downloads

        return data

    @lru_cache(maxsize=500)
    def encoding_lookup(self):
        """ Returns character-encoding for requested document
        """
        resource = self.download_resource()
        return resource['encoding'].lower()

    @lru_cache(maxsize=50)
    def language(self):
        resource = self.download_resource()
        return resource['language']

    @lru_cache(maxsize=50)
    def request_start(self):
        """ When the Class was instantiated """
        return self.request_start

    def request_stop(self):
        """ Finish time of the last download """
        return self.request_stop

    def elapsed_time(self):
        """ Elapsed time between instantiation and last download """
        return self.request_stop - self.request_start

    def increment_num_downloads(self) -> int:
        """ Increment download counter """
        self.num_downloads = self.num_downloads + 1
        return self.num_downloads

    def num_downloads(self):
        """ Number of time class has downloaded a page.
            This Metric used to tell if class is caching properly
            If it is not, the class will requery the url multiple times
        """
        return self.num_downloads


# ################## Non-class functions #######################

def convert_quotes_to_straight(str):
    """ TODO: I'm cutting corners on typography until I figure out how to
        standardize curly and straight quotes better.

        The problem I'm trying to solve is that a quote may use a different
        style of quote or apostrophe symbol than its source,
        but I still want the quotes match it, so I'm converting
        all quotes and apostrophes to the straight style.
    """
    if str:  # check to see if str isn't empty
        str = str.replace("”", '"')
        str = str.replace("“", '"')
        str = str.replace("’", "'")

        str = str.replace('&#39;', "'")
        str = str.replace('&apos;', "'")
        str = str.replace(u'\xa0', u' ')
        str = str.replace('&\rsquo;', "'")
        str = str.replace('&lsquo;', "'")

        str = str.replace('&rsquo;', '"')
        str = str.replace('&lsquo;', '"')
        str = str.replace("\201C", '"')
        str = str.replace(u"\u201c", "")
        str = str.replace(u"\u201d", "")
    return str

def normalize_whitespace(str):
    """
        Convert multiple spaces and space characters to a single space.
        Trim space at the beginning and end of the string
    """
    if str:  # check to see if str isn't empty
        str = str.replace("&nbsp;", " ")
        str = str.replace(u'\xa0', u' ')
        str = str.strip()               # trim whitespace at beginning and end
        str = re.sub(r'\s+', ' ', str)  # convert multiple spaces into single space
    return str


def format_filename(filename):
    folder_separator = "%2"
    return filename.replace("/", folder_separator)

# --------------- Media Providers: Transcript diffferent for URL Type ------------#

# Oyez: Supreme Court Transcripts

def get_domain(public_url):
    from urllib.parse import urlparse
    parsed_uri = urlparse(public_url)
    domain = '{uri.netloc}'.format(uri=parsed_uri)
    return domain

def oyez_public_json(public_apps_url):
    # Lookup case_id from apps url and return api url
    json_url = ''

    # Make sure the domain is Oyez:
    ext = tldextract.extract(public_apps_url)
    if (ext.domain == 'oyez' and ext.suffix == 'org'):
        case_id = re.match('.*?([0-9]+)$', public_apps_url).group(1)
        json_url = 'https://api.oyez.org/case_media/oral_argument_audio/' + case_id
    else:
        print("NOT: oyez.org")

    return json_url


def oyez_transcript(public_url):
    # Convert public json url to text transcript
    json_url = oyez_public_json(public_url)

    if (len(json_url) == 0):
        print("NOT: " + json_url)
        return ''

    else:
        print("OYEZ JSON: " + json_url)

        output = ''
        line_output = ''

        r = requests.get(url=json_url)
        data = r.json()  # Check the JSON Response Content documentation below

        for num, sections in enumerate(data['transcript']['sections']):

            for turns in sections['turns']:
                turn_num = 0

                for section_dict in turns:
                    section_num = 0

                    for text in turns['text_blocks']:
                        if (text['text'] != line_output):

                            if (turn_num == 0):
                                output = output + text['text'] + "\n\n"
                            line_output = text['text']

                        section_num = section_num + 1

                    turn_num = turn_num + 1

        return output


def youtube_video_id(value):
    # Get id from YouTube URL
    # Credit: https://stackoverflow.com/questions/4356538/how-can-i-extract-video-id-from-youtubes-link-in-python

    """
    Examples:
    - http://youtu.be/SA2iWivDJiE
    - http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu
    - http://www.youtube.com/embed/SA2iWivDJiE
    - http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US
    """
    query = urlparse(value)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            p = parse_qs(query.query)
            return p['v'][0]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]
    # fail?
    return None


def youtube_transcript(url):

    transcript_output = ''

    ydl = youtube_dl.YoutubeDL(
        {   'writesubtitles': True,
            'allsubtitles': True,
            'writeautomaticsub': True
        }
    )

    res = ydl.extract_info(url, download=False)
    youtube_id = youtube_video_id(url)

    if res['requested_subtitles'] and res['requested_subtitles'][
        'en']:
        print('Grabbing vtt file from ' +
              res['requested_subtitles']['en']['url'])
        response = requests.get(
            res['requested_subtitles']['en']['url'],
            stream=True
        )
        f1 = open("../transcripts/" + youtube_id + ".txt", "w")

        text = response.text

        import itertools
        import re

        # Remove Formatting: time & color ccodes
        # Credit: Alex Chan
        # Source: https://github.com/alexwlchan/junkdrawer/blob/d8ee4dee1b89181d114500b6e2d69a48e2a0e9c1/services/youtube/vtt2txt.py

        # Throw away the header, which is of the form:
        #
        #     WEBVTT
        #     Kind: captions
        #     Language: en
        #     Style:
        #     ::cue(c.colorCCCCCC) { color: rgb(204,204,204);
        #      }
        #     ::cue(c.colorE5E5E5) { color: rgb(229,229,229);
        #      }
        #     ##
        #

        #>>>>>>>>>>>text = text.split("##\n", 1)[1]

        # Now throw away all the timestamps, which are typically of
        # the form:
        #
        #     00:00:01.819 --> 00:00:01.829 align:start position:0%
        #
        text, _ = re.subn(
            r'\d{2}:\d{2}:\d{2}\.\d{3} \-\-> \d{2}:\d{2}:\d{2}\.\d{3} align:start position:0%\n',
            '',
            text
        )

        # And the color changes, e.g.
        #
        #     <c.colorE5E5E5>
        #
        text, _ = re.subn(r'<c\.color[0-9A-Z]{6}>', '', text)

        # And any other timestamps, typically something like:
        #
        #    </c><00:00:00,539><c>
        #
        # with optional closing/opening tags.
        text, _ = re.subn(r'(?:</c>)?(?:<\d{2}:\d{2}:\d{2}\.\d{3}>)?(?:<c>)?',
                          '', text)

        # 00:00:03,500 --> 00:00:03,510
        text, _ = re.subn(
            r'\d{2}:\d{2}:\d{2}\.\d{3} \-\-> \d{2}:\d{2}:\d{2}\.\d{3}\n', '',
            text)

        # Now get the distinct lines.
        text = [line.strip() + " " for line in text.splitlines() if line.strip()]

        for line, _ in itertools.groupby(text):
            transcript_output += line + " "

        transcript_output = transcript_output.replace("\n", " ")
        transcript_output = transcript_output.replace(": captions", " ")
        transcript_output = transcript_output.replace("Language: en", " ")

        transcript_output = transcript_output.replace("   ", " ")
        transcript_output = transcript_output.replace("  ", " ")
        transcript_output = transcript_output.replace("WEBVTT Kind", " ")
        transcript_output = transcript_output.replace("WEBVTTKind", " ")
        transcript_output = transcript_output.strip()

        f1.write(transcript_output)
        f1.close()

        if len(res['subtitles']) > 0:
            print('manual captions')
        else:
            print('automatic_captions')

    else:
        print('Youtube Video does not have any english captions')

    return transcript_output