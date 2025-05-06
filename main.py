
import dash
from dash import html, dcc, Output, Input, State, dash_table
import plotly.graph_objects as go
import pandas as pd

# Constants
clk_period = 5.0  # Clock period in ns
buffer_delay = 0.5  # Base delay for normal buffer
lvt_factor = 0.7
hvt_factor = 1.3
flop_to_flop_base_delay = 0.0  # Base net delay from FF1 to FF2
setup_time_penalty = 0.2  # Setup time penalty in ns
launch_clock_delay = 0.0  # Launch clock delay in ns

# Dash app setup
app = dash.Dash(__name__)
app.title = "STA Buffer Insertion"

app.layout = html.Div([
    html.H2("STA Visualizer: Add Buffers to the Net"),
    html.Div([
        html.Button("Add Normal Buffer", id="add-buffer", n_clicks=0),
        html.Button("Add LVT Buffer", id="add-lvt", n_clicks=0),
        html.Button("Add HVT Buffer", id="add-hvt", n_clicks=0),
        html.Button("➖ Remove Buffer", id="remove-buffer", n_clicks=0),
        html.Button("♻️ Reset", id="reset", n_clicks=0),
        dcc.Checklist(
            options=[{"label": " Include Setup Time (0.2ns)", "value": "setup"}],
            id="setup-check",
            style={"marginLeft": "40px", "fontSize": "16px"},
            inputStyle={"marginRight": "5px"}
        )
    ], style={"marginBottom": "10px", "display": "flex", "alignItems": "center", "flexWrap": "wrap"}),

    dcc.Graph(id="timing-graph"),

    html.Div(id="timing-info", style={"marginTop": "20px", "fontSize": "18px"}),

    html.Div([
        html.H4("Timing Path Report"),
        html.Div(id="timing-report-table"),
        html.Pre(id="timing-summary", style={"marginTop": "10px", "fontSize": "16px", "backgroundColor": "#f9f9f9", "padding": "10px", "border": "1px solid #ccc"})
    ], style={"marginTop": "20px"})
])

@app.callback(
    Output("timing-graph", "figure"),
    Output("timing-info", "children"),
    Output("timing-report-table", "children"),
    Output("timing-summary", "children"),
    Input("add-buffer", "n_clicks"),
    Input("add-lvt", "n_clicks"),
    Input("add-hvt", "n_clicks"),
    Input("remove-buffer", "n_clicks"),
    Input("reset", "n_clicks"),
    Input("setup-check", "value"),
    prevent_initial_call=True
)
def update_timing_graph(add_clicks, add_lvt, add_hvt, remove_clicks, reset_clicks, setup_check):
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id

    if not hasattr(update_timing_graph, "buffers") or triggered_id == "reset":
        update_timing_graph.buffers = []

    if triggered_id == "add-buffer":
        update_timing_graph.buffers.append(("buffer", buffer_delay))
    elif triggered_id == "add-lvt":
        update_timing_graph.buffers.append(("LVT", buffer_delay * lvt_factor))
    elif triggered_id == "add-hvt":
        update_timing_graph.buffers.append(("HVT", buffer_delay * hvt_factor))
    elif triggered_id == "remove-buffer" and update_timing_graph.buffers:
        update_timing_graph.buffers.pop()

    buffer_list = update_timing_graph.buffers

    cumulative_delay = 0.0
    rows = [
        {"Instance": "startflop", "Incremental Delay": 0.0, "Total Delay": 0.0, "Style": ""}
    ]
    for i, (typ, delay) in enumerate(buffer_list):
        cumulative_delay += delay
        style = "color: red;" if typ == "LVT" else "color: green;" if typ == "HVT" else ""
        rows.append({
            "Instance": f"{typ} buffer{i+1}",
            "Incremental Delay": round(delay, 2),
            "Total Delay": round(cumulative_delay, 2),
            "Style": style
        })
    cumulative_delay += flop_to_flop_base_delay
    rows.append({
        "Instance": "endflop", "Incremental Delay": 0.0, "Total Delay": round(cumulative_delay, 2), "Style": ""})

    arrival_time = cumulative_delay
    setup_penalty = setup_time_penalty if setup_check and "setup" in setup_check else 0.0
    required_time = clk_period - setup_penalty
    slack = required_time - arrival_time

    time_range = [i * 0.1 for i in range(101)]
    launch_clock = [(1 if ((t - launch_clock_delay) % clk_period) < (clk_period / 2) else 0) for t in time_range]
    capture_clock = [(1 if (t % clk_period) < (clk_period / 2) else 0) for t in time_range]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=time_range, y=launch_clock, mode="lines", name="Launch Clock"))
    fig.add_trace(go.Scatter(x=time_range, y=[v + 2 for v in capture_clock], mode="lines", name="Capture Clock"))

    arrow_color = "green" if slack >= 0 else "red"

    fig.add_annotation(
        x=arrival_time, y=3, ax=0, ay=1,
        xref="x", yref="y", axref="x", ayref="y",
        text=f"Delay = {arrival_time:.2f} ns",
        showarrow=True,
        arrowhead=3,
        arrowsize=1.2,
        arrowwidth=2,
        arrowcolor=arrow_color
    )

    if setup_penalty > 0:
        setup_marker_time = clk_period - setup_penalty
        fig.add_shape(
            type="line",
            x0=setup_marker_time, x1=setup_marker_time,
            y0=2, y1=4,
            line=dict(color="orange", width=2, dash="dash"),
            name="Setup Window"
        )

    fig.update_layout(
        title="Clock Waveform with Data Path",
        xaxis_title="Time (ns)",
        yaxis=dict(title="Voltage Level", tickvals=[0, 1, 2, 3], ticktext=["0", "Launch Clock", "0", "Capture Clock"]),
        height=500
    )

    info = f"""
    ⏱ Total Delay: {arrival_time:.2f} ns  
    ✅ Required Time: {required_time:.2f} ns  
    🟢 Slack: {slack:.2f} ns ({'OK' if slack >= 0 else 'Violation!'})
    """

    table = dash_table.DataTable(
        columns=[
            {"name": "Instance", "id": "Instance"},
            {"name": "Incremental Delay (ns)", "id": "Incremental Delay"},
            {"name": "Total Delay (ns)", "id": "Total Delay"}
        ],
        data=rows,
        style_data_conditional=[
            {
                'if': {"filter_query": '{Instance} contains "LVT"'},
                'color': 'red'
            },
            {
                'if': {"filter_query": '{Instance} contains "HVT"'},
                'color': 'green'
            }
        ],
        style_cell={"textAlign": "center"},
        style_header={"backgroundColor": "#e1e1e1", "fontWeight": "bold"},
        style_table={"marginTop": "10px", "border": "1px solid #ccc"}
    )

    summary = (
        f"Startpoint : startflop\n"
        f"Endpoint   : endflop\n"
        f"Pathtype   : setup check\n\n"
        f"Slack = data required time - data arrival time = {required_time:.1f} - {arrival_time:.1f} = {slack:.1f} ({'MET' if slack >= 0 else 'VIOLATED'})"
    )

    return fig, info, table, summary

if __name__ == "__main__":
    app.run(debug=True)
