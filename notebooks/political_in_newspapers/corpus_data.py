import os

import numpy as np
import pandas as pd
import scipy
from gensim.matutils import Sparse2Corpus

from westac.common.utility import flatten

PUBLICATION2ID = {'AFTONBLADET': 1, 'EXPRESSEN': 2, 'DAGENS NYHETER': 3, 'SVENSKA DAGBLADET': 4}
ID2PUBLICATION = {v: k for k, v in PUBLICATION2ID.items()}
ID2PUB = {1: 'AB', 2: 'EX', 3: 'DN', 4: 'SVD'}
PUB2ID = {v: k for k, v in ID2PUB.items()}

corpus_dataset_filename = "corpus_dataset.zip"
document_dataset_filename = "document_dataset.zip"
vocabulary_dataset_filename = "vocabulary_dataset.zip"
censored_corpus_filename = "text1_utantext.zip"
meta_textblocks_filename = "meta_textblocks.zip"
sparse_matrix_filename = "corpus_sparse_doc_term_matrx.npz"
document_processed_filename = "document_processed_dataset.zip"
reconstructed_text_corpus_file = "reconstructed_text_corpus.csv.zip"


def load_corpus_dtm_as_data_frame(corpus_folder):
    """Load corpus DTM, source "dtm1.rds", arrays drm$i, drm$j, drm$v'"""

    filename = os.path.join(corpus_folder, corpus_dataset_filename)

    df_corpus = pd.read_csv(filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False)
    df_corpus.columns = ["document_id", "token_id", "tf"]
    df_corpus.document_id -= 1
    df_corpus.token_id -= 1

    return df_corpus


def load_vocabulary_file_as_data_frame(corpus_folder):
    """Load vocabulary"""

    filename = os.path.join(corpus_folder, vocabulary_dataset_filename)

    df_vocabulary = pd.read_csv(filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False)
    df_vocabulary.columns = ["token"]

    return df_vocabulary


def load_censured_text_as_data_frame(corpus_folder):
    """ Load censored corpus data """

    filename = os.path.join(corpus_folder, censored_corpus_filename)

    df_censured_text = pd.read_csv(filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False)
    df_censured_text.columns = ['id', 'doc_id', 'publication', 'date']
    df_censured_text.id -= 1

    df_censured_text = df_censured_text[['doc_id', 'publication', 'date']].drop_duplicates()

    return df_censured_text


def load_meta_text_blocks_as_data_frame(corpus_folder):
    """ Load censored corpus data """

    filename = os.path.join(corpus_folder, meta_textblocks_filename)
    df_meta = pd.read_csv(filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False)
    df_meta = df_meta[['id', 'pred_bodytext']].drop_duplicates()
    df_meta.columns = ["doc_id", "pred_bodytext"]
    df_meta = df_meta.set_index("doc_id")
    return df_meta


def load_documents(corpus_folder, force=False):
    """ Load documents data, source "dtm1.rds", arrays drm$dimnames[1] """

    processed_filename = os.path.join(corpus_folder, document_processed_filename)

    if not os.path.isfile(processed_filename) or force:

        filename = os.path.join(corpus_folder, document_dataset_filename)

        df_document = pd.read_csv(filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False)
        df_document.columns = ["doc_id"]
        df_document.index.name = 'id'

        # Add publication and date
        df_censured_text = load_censured_text_as_data_frame(corpus_folder)
        df_document = pd.merge(
            df_document,
            df_censured_text[['doc_id', 'publication', 'date']],
            how='inner',
            left_on='doc_id',
            right_on='doc_id',
        )

        # Add pred_bodytext
        df_meta = load_meta_text_blocks_as_data_frame(corpus_folder)
        df_document = pd.merge(df_document, df_meta, how='inner', left_on='doc_id', right_index=True)

        # Add year
        df_document['date'] = pd.to_datetime(df_document.date)
        df_document['year'] = df_document.date.dt.year
        df_document['publication_id'] = df_document.publication.apply(lambda x: PUBLICATION2ID[x]).astype(np.uint16)

        df_document.to_csv(
            processed_filename, compression='zip', header=True, sep=',', quotechar='"', index=True, index_label="id"
        )

    else:
        # loading cached...
        df_document = pd.read_csv(
            processed_filename, compression='zip', header=0, sep=',', quotechar='"', na_filter=False, index_col="id"
        )
        if 'publication_id' not in df_document.columns:
            df_document['publication_id'] = df_document.publication.apply(lambda x: PUBLICATION2ID[x]).astype(np.uint16)

    return df_document


def load(corpus_folder):

    df_corpus = load_corpus_dtm_as_data_frame(corpus_folder)
    df_vocabulary = load_vocabulary_file_as_data_frame(corpus_folder)
    df_document = load_documents(corpus_folder)

    return df_corpus, df_document, df_vocabulary


def load_as_sparse_matrix(corpus_folder):

    filename = os.path.join(corpus_folder, sparse_matrix_filename)

    if not os.path.isfile(filename):
        df_corpus = load_corpus_dtm_as_data_frame(corpus_folder)
        v_dtm = scipy.sparse.coo_matrix((df_corpus.tf, (df_corpus.document_id, df_corpus.token_id)))
        scipy.sparse.save_npz(filename, v_dtm, compressed=True)
    else:
        v_dtm = scipy.sparse.load_npz(filename)

    return v_dtm


def load_reconstructed_text_corpus(corpus_folder):
    filename = os.path.join(corpus_folder, reconstructed_text_corpus_file)
    if not os.path.isfile(filename):
        df_corpus = load_corpus_dtm_as_data_frame(corpus_folder)
        df_vocabulary = load_vocabulary_file_as_data_frame(corpus_folder)
        id2token = df_vocabulary['token'].to_dict()
        df_reconstructed_text_corpus = (df_corpus.groupby('document_id')).apply(
            lambda x: ' '.join(flatten(x['tf'] * (x['token_id'].apply(lambda y: [id2token[y]]))))
        )
        # FIXME Is extra index written? Is headers written? Might be that first row is ignored???
        df_reconstructed_text_corpus.to_csv(filename, compression='zip', header=0, sep=',', quotechar='"')
    else:
        df_reconstructed_text_corpus = pd.read_csv(filename, compression='zip', header=None, sep=',', quotechar='"')
        df_reconstructed_text_corpus.columns = ['document_id', 'text']
        df_reconstructed_text_corpus = df_reconstructed_text_corpus.set_index('document_id')

    return df_reconstructed_text_corpus


def load_as_dtm(corpus_folder):

    dtm = load_as_sparse_matrix(corpus_folder)
    id2token = load_vocabulary_file_as_data_frame(corpus_folder)['token'].to_dict()
    documents = load_documents(corpus_folder)

    return dtm, documents, id2token


def load_as_dtm2(corpus_folder, publication_ids=None):

    dtm, documents, id2token = load_as_dtm(corpus_folder)

    if publication_ids is not None:

        documents = documents[documents.publication_id.isin(publication_ids)]
        dtm = dtm.tocsr()[documents.index, :]
        documents = documents.reset_index().drop('id', axis=1)
        token_ids = dtm.sum(axis=0).nonzero()[1]
        dtm = dtm[:, token_ids]
        id2token = {i: id2token[k] for i, k in enumerate(token_ids)}

    return dtm, documents, id2token


def load_as_gensim_sparse_corpus(corpus_folder):
    dtm, documents, id2token = load_as_dtm(corpus_folder)
    corpus = Sparse2Corpus(dtm, documents_columns=False)
    documents['n_terms'] = np.asarray(corpus.sparse.sum(axis=0)).reshape(-1).astype(np.uint32)
    return corpus, documents, id2token


def load_as_gensim_sparse_corpus2(corpus_folder, publication_ids=None):

    dtm, documents, id2token = load_as_dtm(corpus_folder)

    if publication_ids is not None:
        documents = documents[documents.publication_id.isin(publication_ids)]
        dtm = dtm.tocsr()[documents.index, :]
        documents = documents.reset_index().drop('id', axis=1)
        token_ids = dtm.sum(axis=0).nonzero()[1]
        dtm = dtm[:, token_ids]
        id2token = {i: id2token[k] for i, k in enumerate(token_ids)}

    corpus = Sparse2Corpus(dtm, documents_columns=False)
    documents['n_terms'] = np.asarray(corpus.sparse.sum(axis=0)).reshape(-1).astype(np.uint32)
    return corpus, documents, id2token


def load_dates_subset_as_dtm(corpus_folder, dates):
    dtm, documents, id2token = load_as_dtm(corpus_folder)
    documents = documents[documents.date.isin(dates)]
    dtm = dtm.tocsr()[documents.index, :]
    documents = documents.reset_index().drop('id', axis=1)
    token_ids = dtm.sum(axis=0).nonzero()[1]
    dtm = dtm[:, token_ids]
    id2token = {i: id2token[k] for i, k in enumerate(token_ids)}
    return dtm, documents, id2token


def slim_documents(documents):

    # df = documents[['publication', 'year']].copy()
    # df['publication_id'] = df.publication.apply(lambda x: PUBLICATION2ID[x]).astype(np.uint16)
    # df = df[['publication_id', 'year']]
    return documents[['publication_id', 'year']].copy()


def extend_with_document_info(df, documents):
    """ Adds document meta data to given data frame (must have a document_id) """
    df = df.merge(documents, how='inner', left_on='document_id', right_index=True)
    return df
