import os, sys
import click

root_folder = (lambda d: os.path.join(os.getcwd().split(d)[0], d))("welfare_state_analytics")

sys.path = list(set(sys.path + [ root_folder ]))

import text_analytic_tools.text_analysis.topic_model as topic_model
import westac.corpus.iterators.text_tokenizer as text_tokenizer
import westac.corpus.tokenized_corpus as tokenized_corpus
import westac.common.file_utility as file_utility
from os.path import join as jj
 # pylint: disable=unused-argument, too-many-arguments

CORPUS_FOLDER = os.path.abspath(os.path.join(root_folder, "data"))

@click.command()
@click.argument('name') #, help='Model name.')
@click.option('--n-topics', default=50, help='Number of topics.')
@click.option('--corpus-folder', default=CORPUS_FOLDER, help='Corpus folder (if vectorized corpus exists on disk).')
@click.option('--corpus-filename', help='Corpus filename (if text corpus or Sparv XML). Corpus tag if vectorized corpus.')
@click.option('--engine', default="gensim_lda-multicore", help='LDA implementation')
@click.option('--passes', default=None, help='Number of passes.')
@click.option('--alpha', default='asymmetric', help='Prior belief of topic probability. symmetric/asymmertic/auto')
@click.option('--random-seed', default=None, help="Random seed value")
@click.option('--workers', default=None, help='Number of workers (if applicable).')
@click.option('--max-iter', default=None, help='Max number of iterations.')
@click.option('--prefix', default=None, help='Prefix.')
def _run_model(name, n_topics, corpus_folder, corpus_filename, engine, passes, random_seed, alpha, workers, max_iter, prefix):
    run_model(name, n_topics, corpus_folder, corpus_filename, engine, passes, random_seed, alpha, workers, max_iter, prefix)

def run_model(name, n_topics, corpus_folder, corpus_filename, engine, passes, random_seed, alpha, workers, max_iter, prefix):
    """ runner """

    call_arguments = dict(locals())

    topic_modeling_opts = {
        k: v for k, v in call_arguments.items()
            if k in ['n_topics', 'passes', 'random_seed', 'alpha', 'workers', 'max_iter', 'prefix']
                and v is not None
    }

    transformer_opts = dict(
        only_alphabetic=False,
        only_any_alphanumeric=True,
        to_lower=True,
        min_len=2,
        max_len=99,
        remove_accents=False,
        remove_stopwords=True,
        stopwords=None,
        extra_stopwords=None,
        language="swedish",
        keep_numerals=False,
        keep_symbols=False
    )

    # if SparvTokenizer opts = dict(pos_includes='|NN|', lemmatize=True, chunk_size=None)

    tokenizer = text_tokenizer.TextTokenizer(
        source_path=corpus_filename,
        chunk_size=None,
        filename_pattern="*.txt",
        filename_filter=None,
        fix_hyphenation=True,
        fix_whitespaces=False,
        filename_fields=file_utility.filename_field_parser(['year:_:1', 'sequence_id:_:2'])
    )

    corpus = tokenized_corpus.TokenizedCorpus(
        reader=tokenizer,
        **transformer_opts
    )

    model_data, corpus_data = topic_model.compute(
        terms=corpus.terms,
        doc_term_matrix=None,
        id2word=None,
        documents=corpus.documents,
        method=engine,
        engine_args=topic_modeling_opts
    )

    if corpus_folder is None:
        corpus_folder, _ = os.path.split(os.path.abspath(corpus_filename))

    os.makedirs(jj(corpus_folder, name), exist_ok=True)

    model_data.topic_model.save(jj(corpus_folder, name, 'gensim.model'))

    topic_model.store_model(model_data, jj(corpus_folder, name))

    # corpus_data.document_topic_weights = corpus_data.extend_with_document_info(
    #     corpus_data.document_topic_weights,
    #     corpus.documents
    # )

    corpus_data.store(corpus_folder, name)

# %%

run_model(
    name="SOU-KB-labb-corpus-1945-1989",
    n_topics=200,
    corpus_folder=None,
    corpus_filename="/data/westac/SOU-KB-labb/SOU-KB-labb-corpus-1945-1989.sparv.xml_text_20200923195551.zip",
    engine="gensim_lda",
    random_seed=42,
    alpha="asymmetric",
    passes=None,
    workers=None,
    max_iter=None,
    prefix=None
)

# run_model(
#     name="TEST",
#     n_topics=10,
#     corpus_folder=None,
#     corpus_filename="/data/westac/SOU-KB-labb/test_corpus.zip",
#     engine="gensim_lda",
#     random_seed=42,
#     alpha="asymmetric",
#     passes=None,
#     workers=None,
#     max_iter=None,
#     prefix=None
# )
# %%
# if __name__ == '__main__':
#     _run_model()
