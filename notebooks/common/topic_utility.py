from typing import Dict, Any

import pandas as pd
import text_analytic_tools.utility as utility

#from sklearn.preprocessing import normalize

logger = utility.getLogger('corpus_text_analysis')

def filter_document_topic_weights(document_topic_weights: pd.DataFrame, filters: Dict[str, Any]=None, threshold: float=0.0) -> pd.DataFrame:
    """Returns document's topic weights for given `year`, `topic_id`, custom `filters` and threshold.

    Parameters
    ----------
    document_topic_weights : pd.DataFrame
        Document topic weights
    filters : Dict[str, Any], optional
        [description], by default None
    threshold : float, optional
        [description], by default 0.0

    Returns
    -------
    pd.DataFrame
        [description]
    """
    df = document_topic_weights

    df = df[df.weight >= threshold]

    for k, v in (filters or {}).items():
        if k not in  df.columns:
            logger.warning(f'Column {k} does not exist in dataframe (_find_documents_for_topics)')
            continue
        df = df[df[k] == v]

    return df.copy()

