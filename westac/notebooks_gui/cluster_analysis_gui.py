import types
import ipywidgets
import bokeh
import holoviews as hv
import numpy as np
from markdown import markdown as md
from beakerx import * # pylint: disable=unused-wildcard-import
from beakerx.object import beakerx
from scipy.cluster.hierarchy import dendrogram, linkage

import westac.common.cluster_analysis as cluster_analysis
import westac.common.goodness_of_fit as gof
import westac.notebooks_gui.distributions_plot_gui as pdg
import westac.notebooks_gui.cluster_plot as cluster_plot
import warnings
import westac.common.curve_fit as cf
import itertools

warnings.filterwarnings("ignore", category=FutureWarning)

from westac.common.utility import setup_logger, nth

logger = setup_logger()

DEBUG_CONTAINER = { 'data': None}

def smooth_array(xs, ys, smoothers):
    _xs = xs
    _ys = ys.copy()
    for smoother in smoothers or []:
        _xs, _ys = smoother(_xs, _ys)
    return _xs, _ys

def smooth_matrix(xs, ys_m, smoothers):

    return zip(*[ smooth_array(xs, ys_m[:, i], smoothers) for i in range(0, ys_m.shape[1]) ])

class ClustersMeanPlot:

    def __init__(self, output):

        self.output = output
        self.source = bokeh.models.ColumnDataSource(dict(xs=[], ys=[], color=[], legend=[]))

        with self.output:

            self.plot = cluster_plot.plot_clusters_mean(source=self.source)
            self.handle = bokeh.plotting.show(self.plot, notebook_handle=True)

        self.smoothers = [
            cf.rolling_average_smoother('nearest', 3),
            cf.pchip_spline
        ]

    def update(self, x_corpus, ys_matrix, smoothers=None):

        colors = itertools.cycle(bokeh.palettes.Category20[20])

        smoothers = smoothers or self.smoothers
        xs = x_corpus.xs_years()

        smoothers = None #[]

        ml_xs, ml_ys = smooth_matrix(xs, ys_matrix, smoothers)
        ml_colors = list(itertools.islice(colors, ys_matrix.shape[1]))
        ml_legends = [ 'cluster {}'.format(i) for i in range(0, ys_matrix.shape[1]) ]

        self.source.data = dict(xs=ml_xs, ys=ml_ys, color=ml_colors, legend=ml_legends)

        bokeh.io.push_notebook(self.handle)

class ClustersCountPlot:

    def __init__(self, output):

        self.output = output
        self.plot = None
        # self.source = bokeh.models.ColumnDataSource(dict(cluster=[1,2,3], count=[1,2,3]))

        # with self.output:

        #     self.plot = cluster_plot.plot_clusters_count(source=self.source)
        #     self.handle = bokeh.plotting.show(self.plot, notebook_handle=True)

    def update(self, token_clusters):

        token_counts = token_clusters.groupby('cluster').count()
        colors = itertools.cycle(bokeh.palettes.Category20[20])

        source = dict(
            cluster=[ x for x in token_counts.index ], # [ str(x) for x in token_counts.index ],
            count=[ x for x in token_counts.token ],
            legend=[ 'cluster {}'.format(i) for i in token_counts.index ],
            color=[ next(colors) for i in token_counts.index ]
        )
        # self.source.data = source
        # bokeh.io.push_notebook(self.handle)
        self.output.clear_output()
        with self.output:
            self.plot = cluster_plot.plot_clusters_count(source=source)
            bokeh.plotting.show(self.plot)

def display_gui(x_corpus, df_gof):

    container = types.SimpleNamespace(data=None)

    DEBUG_CONTAINER['data'] = container

    cluster_output_types = [('Scatter', 'scatter'), ('Boxplot', 'boxplot'), ('Table', 'table') ]
    clusters_output_types = [('Bar', 'count'), ('Dendogram', 'dendogram'), ('Table', 'table') ]
    metrics_list = [('L2-norm', 'l2_norm'), ('EMD', 'emd'), ('KLD', 'kld') ]

    n_metric_top_words = [ 10, 100, 250, 500, 1000, 2000, 5000, 10000, 20000 ]

    widgets = types.SimpleNamespace(

        n_cluster_count=ipywidgets.IntSlider(description='#Cluster', min=1, max=200, step=1, value=20,  bar_style='info', continuous_update=False,),
        method_key=ipywidgets.Dropdown(description='Method', options=[('K-means', 'k_means'), ('HCA', 'hca')], value='k_means', layout=ipywidgets.Layout(width='200px')),
        metric=ipywidgets.Dropdown(description='Metric', options=metrics_list, value='l2_norm', layout=ipywidgets.Layout(width='200px')),
        n_metric_top=ipywidgets.Dropdown(description='Words', options=n_metric_top_words, value=5000, layout=ipywidgets.Layout(width='200px'), tooltip="HEJ!"),
        clusters_output_type=ipywidgets.Dropdown(description='Output', options=clusters_output_types, value='count', layout=ipywidgets.Layout(width='200px')),
        compute=ipywidgets.Button(description='Compute', button_style='Success', layout=ipywidgets.Layout(width='100px')),
        progress=ipywidgets.IntProgress(description='', min=0, max=10, step=1, value=0, continuous_update=False, layout=ipywidgets.Layout(width='98%')),

        # cluster_legends=ipywidgets.SelectMultiple(options=[], value=[], rows=30),
        # cluster_legend_map=None,

        clusters_count_output=ipywidgets.Output(),
        clusters_mean_output=ipywidgets.Output(),

        cluster_output_type=ipywidgets.Dropdown(description='Output', options=cluster_output_types, value='boxplot', layout=ipywidgets.Layout(width='200px')),
        threshold=ipywidgets.FloatSlider(description='Threshold', min=0.0, max=1.0, step=0.01, value=0.50,  bar_style='info', continuous_update=False,),
        cluster_index=ipywidgets.Dropdown(description='Cluster', value=None, options=[], bar_style='info', disabled=True, layout=ipywidgets.Layout(width='200px')),
        back=ipywidgets.Button(description="<<", button_style='Success', layout=ipywidgets.Layout(width='40px', color='green'), disabled=True),
        forward=ipywidgets.Button(description=">>", button_style='Success', layout=ipywidgets.Layout(width='40px', color='green'), disabled=True),

        cluster_output=ipywidgets.Output(),
        cluster_words_output=ipywidgets.Output()
    )

    def tick(x=None, p=widgets.progress, max=10): # pylint: disable=redefined-builtin
        if p.max != max: p.max = max
        p.value = x if x is not None else p.value + 1

    def plot_cluster(*args): # pylint: disable=unused-argument

        cluster_output_type = widgets.cluster_output_type.value
        widgets.cluster_output.clear_output()

        if container.data is None:
            return

        token_clusters = container.data.token_clusters

        with widgets.cluster_output:

            tick(1, max=2)

            if cluster_output_type == "scatter":
                p = cluster_plot.plot_cluster(x_corpus, token_clusters, widgets.cluster_index.value, tick=tick)
                bokeh.plotting.show(p)

            if cluster_output_type == "boxplot":
                color = nth(itertools.cycle(bokeh.palettes.Category20[20]), widgets.cluster_index.value)
                p = cluster_plot.plot_cluster_boxplot(x_corpus, token_clusters, widgets.cluster_index.value, color=color)
                p = hv.render(p)
                bokeh.plotting.show(p)

            if cluster_output_type == "table":
                df = token_clusters[token_clusters.cluster==widgets.cluster_index.value]
                display(df)

        tick()
        plot_words()
        tick(0)

    def plot_clusters(*args): # pylint: disable=unused-argument

        output_type = widgets.clusters_output_type.value
        token_clusters = container.data.token_clusters

        if output_type== 'count':
            clusters_count_plot.update(token_clusters)

        with widgets.clusters_count_output:

            if output_type == 'dendrogram' and container.data.key == 'hca':
                dendrogram(linkage(container.data.linkage_matrix, 'ward'))

            if output_type== 'table':
                display(token_clusters)

            if output_type== 'heatmap':
                print('Heatmap: not implemented')

        clusters_mean_plot.update(x_corpus, ys_matrix=container.data.cluster_means().T)

        #widgets.cluster_legends_map = { 'Cluster #{}'.format(x): x for x in token_clusters.cluster.unique().tolist() }
        #widgets.cluster_legends.options = sorted(widgets.cluster_legends_map.keys())
        #idgets.cluster_legends.value = widgets.cluster_legends.options

    def plot_words(*argv): # pylint: disable=unused-argument
        widgets.cluster_words_output.clear_output()
        with widgets.cluster_words_output:
            token_clusters = container.data.token_clusters
            tokens = token_clusters[token_clusters.cluster==widgets.cluster_index.value].token.tolist()
            if len(tokens) > 0:
                pdg.display_gui(x_corpus, tokens, n_columns=3)

    def step_cluster(b):

        if b.description == "<<":
            widgets.cluster_index.value = max(widgets.cluster_index.value - 1, 0)

        if b.description == ">>":
            widgets.cluster_index.value = min(widgets.cluster_index.value + 1, max(widgets.cluster_index.options))

        # plot_cluster()

    def set_method(*args): # pylint: disable=unused-argument

        wth = widgets.threshold
        wnc = widgets.n_cluster_count

        if widgets.method_key.value == 'hca':
            wnc.min, wnc.max, wnc.value = 0, 0, 0
            wth.min, wth.max, wth.value = 0.0, 1.0, 0.5
            wnc.disabled = True
            wth.disabled = False
        else:
            wnc.max, wnc.value, wnc.min = 250, 8, 2
            wnc.disabled = False
            wth.disabled = True

    def threshold_range_changed(*args): # pylint: disable=unused-argument

        if widgets.threshold.disabled is True:
            return

        assert container.data.key == 'hca'

        container.data.set_threshold(widgets.threshold.value)

        widgets.cluster_index.unobserve(plot_cluster, 'value')
        plot_clusters()

        widgets.cluster_index.options = container.data.cluster_labels
        widgets.cluster_index.value = widgets.cluster_index.options[0] if len(widgets.cluster_index.options) > 0 else None
        widgets.cluster_index.observe(plot_cluster, 'value')

        plot_cluster()

    def compute_clicked(*args): # pylint: disable=unused-argument

        widgets.compute.disabled = True
        widgets.cluster_index.disabled = True
        widgets.forward.disabled = True
        widgets.back.disabled = True

        widgets.cluster_output.clear_output()
        widgets.cluster_index.unobserve(plot_cluster, 'value')

        with widgets.cluster_output:
            print("Working, please wait...")

        try:
            widgets.cluster_index.disabled = True
            widgets.cluster_index.value = None
            widgets.cluster_index.options = []

            tick(1, max=10)

            container.data = compute_clusters()
            widgets.cluster_index.options = container.data.cluster_labels
            plot_clusters()
            tick()
            plot_cluster()
            tick(0)

            widgets.cluster_index.disabled = False
            widgets.forward.disabled = False
            widgets.back.disabled = False

            if len(widgets.cluster_index.options) > 0:
                widgets.cluster_index.value = widgets.cluster_index.options[0]

        except Exception as ex: # pylint: disable=broad-except
            with widgets.cluster_output:
                logger.exception(ex)

        widgets.cluster_index.observe(plot_cluster, 'value')
        widgets.compute.disabled = False
        widgets.cluster_index.disabled = False
        widgets.forward.disabled = False
        widgets.back.disabled = False

    def compute_clusters():

        indices, tokens = get_top_tokens_by_metric()

        if widgets.method_key.value == 'k_means':
            corpus_cluster = cluster_analysis.compute_kmeans(x_corpus, indices, tokens, widgets.n_cluster_count.value)
        else:
            corpus_cluster = cluster_analysis.compute_hca(x_corpus, indices, tokens, linkage_method='ward', linkage_metric='euclidean')

        return corpus_cluster

    def get_top_tokens_by_metric():
        df_top = gof.get_most_deviating_words(df_gof, widgets.metric.value, n_count=widgets.n_metric_top.value, ascending=False, abs_value=False)
        tokens = df_top[widgets.metric.value+'_token'].tolist()
        indices = [ x_corpus.token2id[w] for w in tokens ]
        return indices, tokens

    widgets.forward.on_click(step_cluster)
    widgets.back.on_click(step_cluster)
    widgets.compute.on_click(compute_clicked)

    widgets.method_key.observe(set_method, 'value')
    widgets.cluster_index.observe(plot_cluster, 'value')
    widgets.cluster_output_type.observe(plot_cluster, 'value')
    widgets.threshold.observe(threshold_range_changed, 'value')

    widgets_grid = ipywidgets.VBox([
        widgets.progress,
        ipywidgets.HBox([
            ipywidgets.VBox([
                ipywidgets.HBox([
                    ipywidgets.HTML(md("Select method, number of clusters and press compute.")),
                    ipywidgets.VBox([
                        widgets.method_key,
                        widgets.metric,
                        widgets.n_metric_top
                    ]),
                    ipywidgets.VBox([
                        widgets.n_cluster_count,
                        ipywidgets.HBox([widgets.clusters_output_type, widgets.compute])
                    ], layout=ipywidgets.Layout(align_items='flex-end')),
                ]),
                ipywidgets.HTML(md("## Clusters overview")),
                ipywidgets.HBox([
                    widgets.clusters_count_output,
                    widgets.clusters_mean_output,
                    # widgets.cluster_legends
                ])
            ])
        ]),
        ipywidgets.VBox([
            ipywidgets.VBox([
                ipywidgets.HTML(md("## Browse cluster")),
                ipywidgets.HBox([widgets.cluster_output_type, widgets.threshold]),
                ipywidgets.HBox([widgets.cluster_index, widgets.back, widgets.forward]),
                widgets.cluster_output
            ]),
        ]),
        ipywidgets.HTML(md("## Explore words in cluster")),
        widgets.cluster_words_output
    ])
    set_method()
    display(widgets_grid)

    clusters_count_plot = ClustersCountPlot(widgets.clusters_count_output)
    clusters_mean_plot = ClustersMeanPlot(widgets.clusters_mean_output)
