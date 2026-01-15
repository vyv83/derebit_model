# Простой тест чтобы понять как работает cellClicked с множественными гридами
import dash
from dash import dcc, html, Input, Output, callback, ALL
import dash_ag_grid as dag

app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div(id='output'),
    html.Hr(),
    
    html.H4("Grid 1 - 2024-01-01"),
    dag.AgGrid(
        id="grid-2024-01-01",
        rowData=[
            {"strike": 50000, "price_c": 1.5, "price_p": 0.8},
            {"strike": 51000, "price_c": 1.2, "price_p": 1.0},
        ],
        columnDefs=[
            {"field": "strike"},
            {"field": "price_c"},
            {"field": "price_p"},
        ],
    ),
    
    html.Hr(),
    html.H4("Grid 2 - 2024-02-01"),
    dag.AgGrid(
        id="grid-2024-02-01",
        rowData=[
            {"strike": 52000, "price_c": 2.5, "price_p": 1.8},
            {"strike": 53000, "price_c": 2.2, "price_p": 2.0},
        ],
        columnDefs=[
            {"field": "strike"},
            {"field": "price_c"},
            {"field": "price_p"},
        ],
    ),
])

# Попробуем с pattern matching
@callback(
    Output('output', 'children'),
    Input({'type': 'grid', 'date': ALL}, 'cellClicked'),
    prevent_initial_call=True
)
def handle_click(clicks):
    return str(clicks)

if __name__ == "__main__":
    app.run(debug=True, port=8052)
