import os
from westac.common import corpus_vectorizer
from westac.common import text_corpus
from westac.common import vectorized_corpus
from westac.common import file_text_reader

def generate_corpus(filename, output_folder, **kwargs):

    if not os.path.isfile(filename):
        print('error: no such file: {}'.format(filename))
        return

    dump_tag = os.path.basename(filename).split('.')[0]

    if vectorized_corpus.VectorizedCorpus.dump_exists(dump_tag):
        print('notice: removing existing result files...')
        os.remove(os.path.join(output_folder, '{}_vector_data.npy'.format(dump_tag)))
        os.remove(os.path.join(output_folder, '{}_vectorizer_data.pickle'.format(dump_tag)))

    meta_extract = {
        'year': r"SOU (\d{4})\_.*",
        'serial_no': r"SOU \d{4}\_(\d+).*"
    }

    print('Creating new corpus...')
    reader = file_text_reader.FileTextReader(filename, meta_extract=meta_extract, compress_whitespaces=True, dehyphen=True)
    corpus = text_corpus.ProcessedCorpus(reader, **kwargs)

    print('Creating document-term matrix...')
    vectorizer = corpus_vectorizer.CorpusVectorizer()
    v_corpus = vectorizer.fit_transform(corpus)

    print('Saving data matrix...')
    v_corpus.dump(tag=dump_tag, folder=output_folder)

if __name__ == "__main__":

    kwargs = dict(
        isalnum=True,
        to_lower=True,
        deacc=False,
        min_len=2,
        max_len=None,
        numerals=False,
        symbols=False
    )

    filename = './data/SOU_1945-1989.zip'

    generate_corpus(filename, output_folder='./output', **kwargs)