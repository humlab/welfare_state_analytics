# Visualize year-to-topic network by means of topic-document-weights
import types

import bokeh
import ipywidgets as widgets
import penelope.network.metrics as network_metrics
import penelope.network.plot_utility as network_plot
import penelope.network.utility as network_utility
from penelope.utility.utils import extract_counter_items_within_threshold
from .utils import display_document_topics_as_grid
import penelope.notebook.widgets_utils as widget_utils
import penelope.topic_modelling as topic_modelling
import penelope.utility as utility
from ipyaggrid import Grid
from IPython.display import display

from notebooks.common import TopicModelContainer

logger = utility.getLogger("westac")


def get_node_subset_source(network, layout, node_list=None, colors=None):  # pylint: disable=unused-argument

    layout_items = layout.items() if node_list is None else [x for x in layout.items() if x[0] in node_list]

    nodes, nodes_coordinates = zip(*sorted(layout_items))
    xs, ys = list(zip(*nodes_coordinates))

    nodes_source = bokeh.models.ColumnDataSource(
        dict(x=xs, y=ys, name=nodes, node_id=nodes, colors=[colors[x] for x in nodes])
    )
    return nodes_source


def plot_document_topic_network(
    network, layout, scale=1.0, titles=None, focus_topics=None
):  # pylint: disable=unused-argument, too-many-locals
    tools = "pan,wheel_zoom,box_zoom,reset,hover,save"
    year_nodes, topic_nodes = network_utility.get_bipartite_node_set(network, bipartite=0)

    colors = {x: "brown" if x in focus_topics else "skyblue" for x in topic_nodes}

    year_source = network_utility.get_node_subset_source(network, layout, year_nodes)
    topic_source = get_node_subset_source(network, layout, topic_nodes, colors=colors)
    lines_source = network_utility.get_edges_source(network, layout, scale=6.0, normalize=False)

    edges_alphas = network_metrics.compute_alpha_vector(lines_source.data["weights"])

    lines_source.add(edges_alphas, "alphas")

    p = bokeh.plotting.figure(
        plot_width=1000,
        plot_height=600,
        x_axis_type=None,
        y_axis_type=None,
        tools=tools,
    )

    _ = p.multi_line(
        xs="xs",
        ys="ys",
        line_width="weights",
        alpha="alphas",
        level="underlay",
        color="black",
        source=lines_source,
    )
    _ = p.circle(
        x="x",
        y="y",
        size=40,
        source=year_source,
        color="lightgreen",
        line_width=1,
        alpha=1.0,
    )

    r_topics = p.circle(x="x", y="y", size=25, source=topic_source, color="colors", alpha=1.00)

    callback = widget_utils.glyph_hover_callback2(
        topic_source, "node_id", text_ids=titles.index, text=titles, element_id="nx_id1"
    )

    p.add_tools(bokeh.models.HoverTool(renderers=[r_topics], tooltips=None, callback=callback))

    text_opts = dict(
        x="x",
        y="y",
        text="name",
        level="overlay",
        x_offset=0,
        y_offset=0,
        text_font_size="8pt",
    )

    p.add_layout(
        bokeh.models.LabelSet(
            source=year_source, text_color="black", text_align="center", text_baseline="middle", **text_opts
        )
    )
    p.add_layout(
        bokeh.models.LabelSet(
            source=topic_source, text_color="black", text_align="center", text_baseline="middle", **text_opts
        )
    )

    return p



def display_document_topic_network(  # pylint: disable=too-many-locals)
    layout_algorithm,
    inferred_topics: topic_modelling.InferredTopicsData,
    threshold=0.10,
    period=None,
    focus_topics=None,
    scale=1.0,
    output_format="network",
    tick=utility.noop,
):

    tick(1)
    topic_token_weights = inferred_topics.topic_token_weights
    document_topic_weights = inferred_topics.document_topic_weights

    titles = topic_modelling.get_topic_titles(topic_token_weights)

    # df = document_topic_weights[document_topic_weights.weight > threshold].reset_index()

    df_threshold = document_topic_weights[document_topic_weights.weight > threshold].reset_index()

    if len(period or []) == 2:
        df_threshold = df_threshold[(df_threshold.year >= period[0]) & (df_threshold.year <= period[1])]

    df_focus = df_threshold[df_threshold.topic_id.isin(focus_topics)].set_index("document_id")
    df_others = df_threshold[~df_threshold.topic_id.isin(focus_topics)].set_index("document_id")

    df_others = df_others[df_others.index.isin(df_focus.index)]

    df = df_focus.append(df_others).reset_index()

    if len(df) == 0:
        logger.info("No data to show")
        return

    # if len(focus_topics or []) > 0:
    #    df = df[~df.topic_id.isin(focus_topics)]

    df["weight"] = utility.clamp_values(list(df.weight), (0.1, 2.0))

    if "filename" not in df:
        df = df.merge(
            inferred_topics.documents["filename"],
            left_on="document_id",
            right_index=True,
        )

    df["title"] = df.filename

    network = network_utility.create_bipartite_network(df, "title", "topic_id")
    tick()

    if output_format == "network":
        if layout_algorithm == "Circular":
            args = dict(dim=2, center=None, scale=1.0)
        else:
            args = network_plot.layout_args(layout_algorithm, network, scale)
        layout = (network_plot.layout_algorithms[layout_algorithm])(network, **args)
        tick()
        p = plot_document_topic_network(network, layout, scale=scale, titles=titles, focus_topics=focus_topics)
        bokeh.plotting.show(p)

    elif output_format == "table":
        display_document_topics_as_grid(df)

    tick(0)


def display_gui(state: TopicModelContainer):

    lw = lambda w: widgets.Layout(width=w)

    inferred_topics: topic_modelling.InferredTopicsData = state.inferred_topics

    text_id = "nx_id1"
    layout_options = ["Circular", "Kamada-Kawai", "Fruchterman-Reingold"]
    year_min, year_max = inferred_topics.year_period

    n_topics = len(inferred_topics.topic_ids)

    gui = types.SimpleNamespace(
        text=widget_utils.text_widget(text_id),
        period=widgets.IntRangeSlider(
            description="Time",
            min=year_min,
            max=year_max,
            step=1,
            value=(year_min, year_min + 5),
            continues_update=False,
        ),
        scale=widgets.FloatSlider(
            description="Scale",
            min=0.0,
            max=1.0,
            step=0.01,
            value=0.1,
            continues_update=False,
        ),
        threshold=widgets.FloatSlider(
            description="Threshold",
            min=0.0,
            max=1.0,
            step=0.01,
            value=0.10,
            continues_update=False,
        ),
        output_format=widgets.Dropdown(
            description="",
            options={"Network": "network", "Table": "table"},
            value="network",
            layout=lw("200px"),
        ),
        layout=widgets.Dropdown(
            description="",
            options=layout_options,
            value="Fruchterman-Reingold",
            layout=lw("250px"),
        ),
        progress=widgets.IntProgress(min=0, max=4, step=1, value=0, layout=widgets.Layout(width="99%")),
        focus_topics=widgets.SelectMultiple(
            description="",
            options=[("Topic #" + str(i), i) for i in range(0, n_topics)],
            value=[],
            rows=8,
            layout=lw("180px"),
        ),
        button=widgets.Button(description="Display", layout=widgets.Layout(width="99%")),
        output=widgets.Output(),
    )

    def tick(x=None):
        gui.progress.value = gui.progress.value + 1 if x is None else x

    def update_handler(_):

        # if gui.output_format.value == "table":
        #    gui.output.clear_output()
        gui.output.clear_output()

        with gui.output:

            display_document_topic_network(
                layout_algorithm=gui.layout.value,
                inferred_topics=inferred_topics,
                threshold=gui.threshold.value,
                period=gui.period.value,
                focus_topics=gui.focus_topics.value,
                scale=gui.scale.value,
                output_format=gui.output_format.value,
                tick=tick,
            )

    # gui.threshold.observe(update_handler, names='value')
    # gui.period.observe(update_handler, names='value')
    # gui.scale.observe(update_handler, names='value')
    # gui.output_format.observe(update_handler, names='value')
    # gui.layout.observe(update_handler, names='value')
    # gui.focus_topics.observe(update_handler, names='value')
    gui.button.on_click(update_handler)

    w = widgets.VBox(
        [
            widgets.HBox(
                [
                    widgets.VBox([widgets.HTML("Layout"), gui.layout, gui.threshold, gui.scale, gui.period]),
                    widgets.VBox([widgets.HTML("Focus topics"), gui.focus_topics]),
                    widgets.VBox([widgets.HTML("Output"), gui.output_format, gui.progress, gui.button]),
                ]
            ),
            gui.output,
            gui.text,
        ]
    )

    display(w)
    return w
