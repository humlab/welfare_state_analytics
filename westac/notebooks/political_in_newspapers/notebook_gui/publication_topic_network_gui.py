# Visualize year-to-topic network by means of topic-document-weights
import types
import ipywidgets as widgets
import bokeh
import bokeh.plotting
import numpy as np
import text_analytic_tools.text_analysis.derived_data_compiler as derived_data_compiler
import text_analytic_tools.utility.widgets as widgets_helper
import text_analytic_tools.common.network.utility as network_utility
import westac.common.utility as utility
import westac.notebooks.political_in_newspapers.corpus_data as corpus_data

from text_analytic_tools.common.network.plot_utility import layout_algorithms, PlotNetworkUtility
from IPython.display import display

TEXT_ID = 'nx_pub_topic'

def plot_document_topic_network(network, layout, scale=1.0, titles=None):
    tools = "pan,wheel_zoom,box_zoom,reset,hover,previewsave"
    source_nodes, target_nodes = network_utility.get_bipartite_node_set(network, bipartite=0)

    source_source = network_utility.get_node_subset_source(network, layout, source_nodes)
    target_source = network_utility.get_node_subset_source(network, layout, target_nodes)
    lines_source = network_utility.get_edges_source(network, layout, scale=6.0, normalize=False)

    edges_alphas = network_utility.compute_alpha_vector(lines_source.data['weights'])

    lines_source.add(edges_alphas, 'alphas')

    p = bokeh.plotting.figure(plot_width=1000, plot_height=600, x_axis_type=None, y_axis_type=None, tools=tools)

    _ = p.multi_line('xs', 'ys', line_width='weights', level='underlay', alpha='alphas', color='black', source=lines_source)
    _ = p.circle('x','y', size=40, source=source_source, color='lightgreen', line_width=1, alpha=1.0)

    r_topics = p.circle('x','y', size=25, source=target_source, color='skyblue', alpha=1.0)

    p.add_tools(bokeh.models.HoverTool(renderers=[r_topics], tooltips=None, callback=widgets_helper.\
        glyph_hover_callback2(target_source, 'node_id', text_ids=titles.index, text=titles, element_id=TEXT_ID))
    )

    text_opts = dict(x='x', y='y', text='name', level='overlay', x_offset=0, y_offset=0, text_font_size='8pt')

    p.add_layout(
        bokeh.models.LabelSet(
            source=source_source, text_color='black', text_align='center', text_baseline='middle', **text_opts
        )
    )
    p.add_layout(
        bokeh.models.LabelSet(
            source=target_source, text_color='black', text_align='center', text_baseline='middle', **text_opts
        )
    )

    return p

def display_document_topic_network(
    layout_algorithm,
    state,
    document_threshold=0.0,
    mean_threshold=0.10,
    period=None,
    ignores=None,
    scale=1.0,
    aggregate='mean',
    output_format='network',
    tick=utility.noop
):

    tick(1)

    topic_token_weights = state.compiled_data.topic_token_weights
    document_topic_weights = state.compiled_data.document_topic_weights

    titles = derived_data_compiler.get_topic_titles(topic_token_weights)

    df = document_topic_weights
    if len(period or []) == 2:
        df = df[(df.year>=period[0]) & (df.year<=period[1])]

    if len(ignores or []) > 0:
        df = df[~df.topic_id.isin(ignores)]

    df = df[(df['weight'] >= document_threshold)]

    df = df.groupby(['publication_id', 'topic_id']).agg([np.mean, np.max])['weight'].reset_index()
    df.columns = ['publication_id', 'topic_id', 'mean', 'max']

    df = df[(df[aggregate] > mean_threshold)].reset_index()

    if len(df) == 0:
        print('No data! Please change selection.')
        return

    df[aggregate] = utility.clamp_values(list(df[aggregate]), (0.1, 1.0))

    df['publication'] = df.publication_id.apply(lambda x: corpus_data.ID2PUBLICATION[x])
    df['weight'] = df[aggregate]

    network = network_utility.create_bipartite_network(df[['publication', 'topic_id', 'weight']], 'publication', 'topic_id')
    tick()

    if output_format == 'network':
        args = PlotNetworkUtility.layout_args(layout_algorithm, network, scale)
        layout = (layout_algorithms[layout_algorithm])(network, **args)
        tick()
        p = plot_document_topic_network(network, layout, scale=scale, titles=titles)
        bokeh.plotting.show(p)

    else:

        df = df[['publication', 'topic_id',  'weight', 'mean', 'max']]
        df.columns = ['Source', 'Target',  'weight', 'mean', 'max']
        if output_format == 'table':
            display(df)
        if output_format == 'excel':
            filename = utility.timestamp("{}_publication_topic_network.xlsx")
            df.to_excel(filename)
        if output_format == 'CSV':
            filename = utility.timestamp("{}_publication_topic_network.csv")
            df.to_csv(filename, sep='\t')

        display(df)

    tick(0)

def display_gui(state):

    lw = lambda w: widgets.Layout(width=w)

    layout_options = [ 'Circular', 'Kamada-Kawai', 'Fruchterman-Reingold']
    year_min, year_max = state.compiled_data.year_period

    n_topics = state.num_topics

    gui = types.SimpleNamespace(
        text=widgets_helper.text(TEXT_ID),
        period=widgets.IntRangeSlider(description='Time', min=year_min, max=year_max, step=1, value=(year_min, year_max), continues_update=False),
        scale=widgets.FloatSlider(description='Scale', min=0.0, max=1.0, step=0.01, value=0.1, continues_update=False),
        document_threshold=widgets.FloatSlider(description='Threshold(D)', min=0.0, max=1.0, step=0.01, value=0.00, continues_update=False),
        mean_threshold=widgets.FloatSlider(description='Threshold(G)', min=0.0, max=1.0, step=0.01, value=0.10, continues_update=False),
        aggregate=widgets.Dropdown(description='Aggregate', options=['mean', 'max'], value='mean', layout=widgets.Layout(width="200px")),
        output_format=widgets.Dropdown(description='Output', options={ 'Network': 'network', 'Table': 'table', 'Excel': 'excel', 'CSV': 'csv' }, value='network', layout=lw('200px')),
        layout=widgets.Dropdown(description='Layout', options=layout_options, value='Fruchterman-Reingold', layout=lw('250px')),
        progress=widgets.IntProgress(min=0, max=4, step=1, value=0, layout=widgets.Layout(width="99%")),
        ignores=widgets.SelectMultiple(description='Ignore', options=[('', None)] + [ ('Topic #'+str(i), i) for i in range(0, n_topics) ], value=[], rows=8, layout=lw('240px')),
    )

    def tick(x=None):
        gui.progress.value = gui.progress.value + 1 if x is None else x

    iw = widgets.interactive(
        display_document_topic_network,
        layout_algorithm=gui.layout,
        state=widgets.fixed(state),
        document_threshold=gui.document_threshold,
        mean_threshold=gui.mean_threshold,
        period=gui.period,
        ignores=gui.ignores,
        scale=gui.scale,
        aggregate=gui.aggregate,
        output_format=gui.output_format,
        tick=widgets.fixed(tick)
    )

    display(widgets.VBox([
        widgets.HBox([
            widgets.VBox([gui.layout, gui.document_threshold, gui.mean_threshold, gui.scale, gui.period]),
            widgets.VBox([gui.ignores]),
            widgets.VBox([gui.output_format, gui.progress]),
        ]),
        iw.children[-1],
        gui.text,
    ]))
    iw.update()

