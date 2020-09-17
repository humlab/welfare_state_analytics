# -*- coding: utf-8 -*-
import logging

import westac.common.zip_utility as zip_utility

from westac.corpus.sparv.sparv_xml_to_text import SparvXml2Text, XSLT_FILENAME_V3

from .corpus_source_reader import CorpusSourceReader

logger = logging.getLogger(__name__)

class SparvXmlCorpusSourceReader(CorpusSourceReader):

    def __init__(self, source, transforms=None, postags=None, lemmatize=True, chunk_size=None, xslt_filename=None, deliminator="|", append_pos="", ignores="|MAD|MID|PAD|"):

        tokenize = lambda x: str(x).split(deliminator)

        super(SparvXmlCorpusSourceReader, self).__init__(source, transforms, chunk_size, pattern='*.xml', tokenize=tokenize, as_binary=True)

        self.postags = postags
        self.lemmatize = lemmatize
        self.append_pos = append_pos
        self.ignores = ignores

        self.parser = SparvXml2Text(xslt_filename=xslt_filename, postags=postags, lemmatize=lemmatize, append_pos=append_pos, ignores=ignores)

    def preprocess(self, content):

        return self.parser.transform(content)

class Sparv3XmlCorpusSourceReader(SparvXmlCorpusSourceReader):

    def __init__(self, source, transforms=None, postags=None, lemmatize=True, chunk_size=None, deliminator="|", append_pos="", ignores="|MAD|MID|PAD|"):

        super(Sparv3XmlCorpusSourceReader, self).__init__(
            source,
            transforms=transforms,
            postags=postags,
            lemmatize=lemmatize,
            chunk_size=chunk_size,
            xslt_filename=XSLT_FILENAME_V3,
            deliminator=deliminator,
            append_pos=append_pos,
            ignores=ignores
        )


def sparv_extract_and_store(source, target, **opts):

    stream = SparvXmlCorpusSourceReader(source, **opts)

    zip_utility.store_text_to_archive(target, stream)
