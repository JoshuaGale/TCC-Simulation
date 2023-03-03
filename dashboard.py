from concurrent.futures import process
from multiprocessing.sharedctypes import Value
import dash
from dash import html
from dash import dcc
from energy_model import *
import numpy as np
import json, os
from datetime import datetime
from datetime import timedelta
from dash import Dash, Input, Output, ctx, State, MATCH, ALL
import plotly.express as px
import pandas as pd
from pandas import DataFrame
from tkinter.filedialog import asksaveasfile
from tkinter.filedialog import askopenfile
from tkinter import ttk, filedialog
import xlsxwriter


# Path to the configuration file used for the model
generalFile = r"C:\Users\JoshuaGale\OneDrive - GPOne Consulting\TCC api\TCC Work In\Important Files\DataSimulation\TCC-Simulation\simulation_config.json"
if os.path.isfile(generalFile):
    with open(generalFile) as f:
        configFile = json.load(f)

def simulate_model(configFile):
    # Values we are taking out of the model for display
    all_energyStorageUtilized = []
    all_networkEnergyGenerated = []
    all_networkEnergyDemand = []
    all_networkAverageEnergyLevel = []
    all_networkTotalEnergySold = []
    all_networkTotalEnergyBought = []
    all_networkAverageTemperature = []
    all_networkBatteryPercent = []
    all_newBoughtAndSold = []

    buildingGenerationValues = {}
    buildingConsumptionValues = {}
    buildingNetValues = {}
    buildingBatteryLoad = {}

    # Given timestamp in string
    print(configFile.get("StartDateTime"))
    print(isinstance(configFile.get("StartDateTime"), str))
    if isinstance(configFile.get("StartDateTime"), str):
        time_str = configFile.get("StartDateTime")
        date_format_str = '%Y-%m-%dT%H:%M:%S'
        # create datetime object from timestamp string
        startDateTime = datetime.strptime(time_str, date_format_str)
    else:
        startDateTime = configFile.get("StartDateTime")
    yToTime = [] 

    configFile["StartDateTime"] = startDateTime
    model = EnergyModel(configFile)

    for agent in model.schedule.agents:
        buildingGenerationValues[agent.name] = [] 
        buildingConsumptionValues[agent.name] = [] 
        buildingNetValues[agent.name] = [] 
        buildingBatteryLoad[agent.name] = [] 


    print(len(model.schedule.agents))
    # How many steps the model runs for, calculate the totals from the agents
    #131040 = 3 months, 1440 = 1 day
    for i in range(configFile["SimulationRuntime"]):
        yToTime.append(startDateTime + timedelta(minutes=float(i)))
        model.step()
        total_energyStorageUtilized = 0
        total_networkAverageEnergyLevel = 0
        total_networkBatteryCapacity = 0
        total_networkEnergyGenerated = 0
        total_networkEnergyDemand = 0
        total_averageTemperature = 0

        for agent in model.schedule.agents:
            total_energyStorageUtilized += agent.energyStorageUtilized
            total_networkBatteryCapacity += agent.energyStorageCapacity
            total_networkEnergyGenerated += agent.energyProduction
            total_networkEnergyDemand += agent.energyConsumption
            buildingGenerationValues[agent.name].append(agent.energyProduction / 1000)
            buildingConsumptionValues[agent.name].append(agent.energyConsumption / 1000)
            buildingNetValues[agent.name].append((agent.energyConsumption / 1000) - (agent.energyProduction / 1000))
            buildingBatteryLoad[agent.name].append(agent.amountToChargeOrDischarge / 1000)

        total_networkAverageEnergyLevel += model.stepEnergyLevel
        if total_networkBatteryCapacity > 0:
            all_networkBatteryPercent.append((total_energyStorageUtilized / total_networkBatteryCapacity) * 100)

        if i == 0:
            all_networkTotalEnergyBought.append((-min(total_networkAverageEnergyLevel, 0)) / 1000 / 60)
            all_networkTotalEnergySold.append((max(total_networkAverageEnergyLevel, 0)) / 1000 / 60)
        else:
            all_networkTotalEnergySold.append((max(total_networkAverageEnergyLevel, 0) + all_networkTotalEnergySold[-1] * 1000 * 60) / 1000 / 60)
            all_networkTotalEnergyBought.append((-min(total_networkAverageEnergyLevel, 0) + all_networkTotalEnergyBought[-1] * 1000 * 60) / 1000 / 60)

        all_newBoughtAndSold.append(all_networkTotalEnergyBought[-1] - all_networkTotalEnergySold[-1])
        all_networkEnergyGenerated.append(total_networkEnergyGenerated / 1000)
        all_networkEnergyDemand.append(total_networkEnergyDemand / 1000)
        all_energyStorageUtilized.append(total_energyStorageUtilized)
        all_networkAverageEnergyLevel.append(-total_networkAverageEnergyLevel / 1000)
        all_networkAverageTemperature.append(total_averageTemperature)

    #post simulation processing
    mapData = {'data': {'lat': [], 'lon': [], 'building': [], 'Net Energy (kW)': []}}
    for agent in model.schedule.agents:
            mapData.get("data").get("lat").append(agent.location[0])
            mapData.get("data").get("lon").append(agent.location[1])
            mapData.get("data").get("building").append(agent.name)
            mapData.get("data").get("Net Energy (kW)").append(agent.totalEnergyLocalNetworkContribution / 1000)


    return {"yToTime":yToTime, "BatteryPercentage": all_networkBatteryPercent, "TotalEnergyBought": all_networkTotalEnergyBought, "TotalEnergySold": all_networkTotalEnergySold, "BoughtAndSold": all_newBoughtAndSold, "EnergyGenerated": all_networkEnergyGenerated, "EnergyDemand": all_networkEnergyDemand, "StorageUtilized": all_energyStorageUtilized, "AverageEnergyLevel": all_networkAverageEnergyLevel, "AverageTemperature": all_networkAverageTemperature, "buildingGenerationValues": buildingGenerationValues, "buildingConsumptionValues": buildingConsumptionValues, "buildingNetValues": buildingNetValues, "buildingBatteryLoad": buildingBatteryLoad, "mapData": mapData} 

processedData = simulate_model(configFile)
all_energyStorageUtilized = processedData.get("StorageUtilized")
all_networkEnergyGenerated = processedData.get("EnergyGenerated")
all_networkEnergyDemand = processedData.get("EnergyDemand")
all_networkAverageEnergyLevel = processedData.get("AverageEnergyLevel")
all_networkTotalEnergySold = processedData.get("TotalEnergySold")
all_networkTotalEnergyBought = processedData.get("TotalEnergyBought")
all_networkAverageTemperature = processedData.get("AverageTemperature")
all_networkBatteryPercent = processedData.get("BatteryPercentage")
all_newBoughtAndSold = processedData.get("BoughtAndSold")
buildingGenerationValues = processedData.get("buildingGenerationValues")
buildingConsumptionValues = processedData.get("buildingConsumptionValues")
buildingNetValues = processedData.get("buildingNetValues")
buildingBatteryLoad = processedData.get("buildingBatteryLoad")
yToTime = processedData.get("yToTime")

mapDF = pd.DataFrame(data = processedData.get("mapData").get("data"))

siteMap = px.scatter_mapbox(mapDF, lat="lat", lon="lon", hover_name="building", zoom=10, height=300, color="Net Energy (kW)", color_continuous_scale=px.colors.sequential.Bluered)
siteMap.update_layout(mapbox_style="open-street-map")
siteMap.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

buildingGraphs = []

menuChildren = [html.Div(className="input-pair submit-button", children=[
            html.Div(id='label_StartDateTime', children="Start Date Time:"),
            html.Div(dcc.DatePickerSingle(id='input-StartDateTime',  date=configFile.get('StartDateTime')))
            ]),
            html.Div(className="input-pair submit-button", children=[
            html.Div(id='SimulationRuntime', children="Simulation Runtime (minutes):"),
            html.Div(dcc.Input(id='input-SimulationRuntime', type="number", value=configFile.get('SimulationRuntime')))
            ]),
            html.Div(className="input-pair submit-button", children=[
            html.Div(id='energy-buy-cost', children="Energy Purchase Price ($):"),
            html.Div(dcc.Input(id='input-energy-buy-cost', type="number", value=configFile.get('EnergyBuyPricePerKW')))
            ]),
            html.Div(className="input-pair submit-button", children=[
            html.Div(id='energy-sell-cost', children="Energy Sell Price ($):"),
            html.Div(dcc.Input(id='input-energy-sell-cost', type="number", value=configFile.get('EnergySellPricePerKW')))
            ]),
            html.Div(className="input-pair submit-button", children=[
            html.Div(id='label-total-energy-cost', children="Total Energy Cost ($): "),
            html.Div(id='total-energy-cost', children="{}".format(0)),
            ])]
index = 0
for building in configFile.get("Buildings"):
    buildingChildren = [html.Div(id='label-' + building.get("name"), children=building.get("name"))]
    buildingChildren.append(html.Div(className="input-pair", children=[
            html.Div(id={'type':'label-energyStorageCapacityKWH', 'index': index}, children='Energy Storage Capacity (KWH) ' + ":"),
            html.Div(dcc.Input(id={'type':'input-energyStorageCapacityKWH', 'index': index}, type="number", value=building.get("energyStorageCapacityKWH")))
            ]))
    buildingChildren.append(html.Div(className="input-pair", children=[
            html.Div(id={'type':'label-energyStorageChargeAndDischargeRateKW', 'index': index}, children='Energy Storage Charge And Discharge Rate (KW) ' + ":"),
            html.Div(dcc.Input(id={'type':'input-energyStorageChargeAndDischargeRateKW', 'index': index}, type="number",  value=building.get("energyStorageChargeAndDischargeRateKW")))
            ]))
    buildingChildren.append(html.Div([
            html.Div(id={'type':'label-battery-model', 'index': index}, children='Battery Model' + ":"),
            dcc.Dropdown(['Simple', 'Complex'], 'Simple', id={'type':'dropdown-battery-model', 'index': index})
            ]))
    for buildingComponent in building.get("buildingComponents"):
        if buildingComponent.get("name") == "Solar Generation":
            buildingChildren.append(html.Div(className="input-pair", children=[
                html.Div(id={'type':'label-SolarGeneration', 'index': index}, children='Extra Solar System Size (KW) ' + ":"),
                html.Div(dcc.Input(id={'type':'input-SolarGeneration', 'index': index}, type="number",  value=buildingComponent.get("systemSizeKW")))
                ]))
        if buildingComponent.get("name") == "Solar Sample":
            buildingChildren.append(html.Div(className="input-pair", children=[
                html.Div(id={'type':'label-SolarScale', 'index': index}, children='Solar System Scale (KW) ' + ":"),
                html.Div(dcc.Input(id={'type':'input-SolarScale', 'index': index}, type="number",  value=buildingComponent.get("multiplicationFactor")))
                ]))
    menuChildren.append(html.Div(className="building-layout", children=buildingChildren))

    buildingGraphs.append(html.Div(
        className="sub-layout",
        children=[
        dcc.Graph(
            id={'type':'building-graph', 'index': index},
            style={'height': 400},
            figure={
                'data': [{
                    'y': buildingGenerationValues[building.get("name")],
                    'x': yToTime
                },
                {
                    'y': buildingConsumptionValues[building.get("name")],
                    'x': yToTime
                },
                {
                    'y': buildingNetValues[building.get("name")],
                    'x': yToTime
                }]
        }
    )]))
    index += 1

menuChildren.append(html.Button('Submit', className="submit-button", id='submit-val', n_clicks=0))
menuChildren.append(html.Button('Save', className="submit-button", id='saveconfig-val', n_clicks=0))
menuChildren.append(html.Button('Load', className="submit-button", id='loadconfig-val', n_clicks=0))


menuChildren.append(html.Div(className="input-pair submit-button", children=[
            html.Div(id='label_NewLocationName', children="Name:"),
            html.Div(dcc.Input(id='input-NewLocationName', type="text", value=""))
            ]))
menuChildren.append(html.Button('Add Location', className="submit-button", id='addLocation-val', n_clicks=0))


### Create new Location Controls



app = dash.Dash(__name__)

app.layout = html.Div(
    className="main-layout",
    children=[
        html.Div(
        className="menu-layout",
        children=menuChildren
        ),

    html.Div(
        className="sub-layout",
        children=[
        dcc.Graph(
        id='graph-1',
        style={
           'height': 400
        },
        figure={
            'data': [{
                'y': all_networkAverageEnergyLevel,
                'x': yToTime
            }]
        }
    )]),
    html.Div(
        className="sub-layout",
        children=[
        dcc.Graph(
        id='graph-2',
       style={
           'height': 400
       },
        figure={
            'data': [{
                'y': all_networkTotalEnergySold,
                'x': yToTime
            },
            {
                'y': all_networkTotalEnergyBought,
                'x': yToTime
            }]
        }
    )]),
    html.Div(
        className="sub-layout",
        children=[
        dcc.Graph(
        id='graph-3',
       style={
           'height': 400
       },
        figure={
            'data': [{
                'y': all_networkEnergyGenerated,
                'x': yToTime
            },
            {
                'y': all_networkEnergyDemand,
                'x': yToTime
            }]
        }
    )]),
    html.Div(
        className="sub-layout",
        children=[
        dcc.Graph(
        id='graph-battery',
       style={
           'height': 400
       },
        figure={
            'data': [{
                'y': all_networkBatteryPercent,
                'x': yToTime
            }]
        }
    )]),
    *buildingGraphs,
    html.Div(
        className="menu-layout",
        children=[
        dcc.Graph(
        id='map-1',
        style={
           'height': 400
       },
        figure=siteMap
    )]),
    dcc.Store(id='session-config', data=configFile)

])

@app.callback(
    Output({'type': 'building-graph', 'index': ALL}, 'figure'),
    Output('graph-1', 'figure'),
    Output('graph-2', 'figure'),
    Output('graph-3', 'figure'),
    Output('graph-battery', 'figure'),
    Output('total-energy-cost', 'children'),
    State('session-config', 'data'),
    State({'type': 'input-energyStorageCapacityKWH', 'index': ALL}, 'value'),
    State({'type': 'input-energyStorageChargeAndDischargeRateKW', 'index': ALL}, 'value'),
    State({'type': 'dropdown-battery-model', 'index': ALL}, 'value'),
    State({'type': 'input-SolarGeneration', 'index': ALL}, 'value'),
    State({'type': 'input-SolarScale', 'index': ALL}, 'value'),
    State('input-StartDateTime', 'date'),
    State('input-SimulationRuntime', 'value'),
    State('input-energy-sell-cost', 'value'),
    State('input-energy-buy-cost', 'value'),
    Input('submit-val', 'n_clicks')
)
def update_graphs(data, energyStorageCapacityKWH, energyStorageChargeAndDischargeRateKW, dropdownBatteryModel, solarSize, solarScale, startDateTime, simulationRuntime, energySellPrice, energyBuyPrice, clicks):
    if 'T00:00:00' not in startDateTime:
        startDateTime = startDateTime + 'T00:00:00'
    data["SimulationRuntime"] = simulationRuntime
    data["StartDateTime"] = startDateTime
    for i, building in enumerate(data.get("Buildings")):
        building["energyStorageCapacityKWH"] = energyStorageCapacityKWH[i]
        building["energyStorageChargeAndDischargeRateKW"] = energyStorageChargeAndDischargeRateKW[i]
        building["batteryModel"] = dropdownBatteryModel[i]
        for buildingComponent in building.get("buildingComponents"):
            if buildingComponent.get("name") == "Solar Generation":
                buildingComponent["systemSizeKW"] = solarSize[i]
            if buildingComponent.get("name") == "Solar Sample":
                buildingComponent["multiplicationFactor"] = solarScale[i]

    processedData = simulate_model(data)
    totalEnergyCost = processedData.get("TotalEnergyBought")[-1] * energyBuyPrice - processedData.get("TotalEnergySold")[-1] * energySellPrice
    
    updateBuildingGraphs = []
    for building in data.get("Buildings"):
        updateBuildingGraphs.append(
            {
                'data': [
                    {
                    'y': processedData.get("buildingGenerationValues")[building.get("name")],
                    'x': processedData.get("yToTime"),
                    'name': 'Energy Generation (kW)'
                },
                {
                    'y': processedData.get("buildingConsumptionValues")[building.get("name")],
                    'x': processedData.get("yToTime"),
                    'name': 'Energy Demand (kW)'
                },
                {
                    'y': processedData.get("buildingNetValues")[building.get("name")],
                    'x': processedData.get("yToTime"),
                    'name': 'Energy Demand to network (kW)'
                },
                {
                    'y': processedData.get("buildingBatteryLoad")[building.get("name")],
                    'x': processedData.get("yToTime"),
                    'name': 'Battery Demand (kW)'
                }
                ],
                'layout': {
                    'title': building.get("name")
                }
            }
            )    
    
    averageEnergyGraph = {
            'data': [{
                'y': processedData.get("AverageEnergyLevel"),
                'x': processedData.get("yToTime"),
                'name': 'Average Energy Level'
            }],
            'layout': {
                'title': 'Average Energy Level'
            }
            }
    energyTransactionGraph = {
            'data': [{
                'y': processedData.get("TotalEnergySold"),
                'x': processedData.get("yToTime"),
                'name': 'Total Energy Sold'
            },
            {
                'y': processedData.get("TotalEnergyBought"),
                'x': processedData.get("yToTime"),
                'name': 'Total Energy Bought'
            }],
            'layout': {
                'title': 'Total Energy Sold / Bought'
            }
        }
    energyGeneratedGraph = {
            'data': [{
                'y': processedData.get("EnergyGenerated"),
                'x': processedData.get("yToTime"),
                'name': 'Energy Generated'
            },
            {
                'y': processedData.get("EnergyDemand"),
                'x': processedData.get("yToTime"),
                'name': 'Energy Demand'
            }],
            'layout': {
                'title': 'Network Energy Generation and Demand'
            }
        }
    graphBattery = {
            'data': [{
                'y': processedData.get("BatteryPercentage"),
                'x': processedData.get("yToTime"),
                'name': 'Energy Generated'
            }],
            'layout': {
                'title': 'Network Battery Energy Stored'
            }
        }
  
    return updateBuildingGraphs, averageEnergyGraph, energyTransactionGraph, energyGeneratedGraph, graphBattery, totalEnergyCost


@app.callback(
    Output('session-config', 'data'),
    Output({'type': 'input-energyStorageCapacityKWH', 'index': ALL}, 'value'),
    Output({'type': 'input-energyStorageChargeAndDischargeRateKW', 'index': ALL}, 'value'),
    Output({'type': 'dropdown-battery-model', 'index': ALL}, 'value'),
    Output({'type': 'input-SolarGeneration', 'index': ALL}, 'value'),
    Output({'type': 'input-SolarScale', 'index': ALL}, 'value'),
    Output('input-StartDateTime', 'date'),
    Output('input-SimulationRuntime', 'value'),
    Output('input-energy-sell-cost', 'value'),
    Output('input-energy-buy-cost', 'value'),
    State('session-config', 'data'),
    State({'type': 'input-energyStorageCapacityKWH', 'index': ALL}, 'value'),
    State({'type': 'input-energyStorageChargeAndDischargeRateKW', 'index': ALL}, 'value'),
    State({'type': 'dropdown-battery-model', 'index': ALL}, 'value'),
    State({'type': 'input-SolarGeneration', 'index': ALL}, 'value'),
    State({'type': 'input-SolarScale', 'index': ALL}, 'value'),
    State('input-StartDateTime', 'date'),
    State('input-SimulationRuntime', 'value'),
    State('input-energy-sell-cost', 'value'),
    State('input-energy-buy-cost', 'value'),
    State('input-NewLocationName', 'value'),
    Input('saveconfig-val', 'n_clicks'),
    Input('loadconfig-val', 'n_clicks'),
    Input('addLocation-val', 'n_clicks')

)
def save_config(data, energyStorageCapacityKWH, energyStorageChargeAndDischargeRateKW, dropdownBatteryModel, solarSize, solarScale, startDateTime, simulationRuntime, energySellPrice, energyBuyPrice, newLocationName, saveClicks, loadClicks, newLocationClicks):
    if 'T00:00:00' not in startDateTime:
        startDateTime = startDateTime + 'T00:00:00'
    data["SimulationRuntime"] = simulationRuntime
    data["StartDateTime"] = startDateTime
    print(data.get("Buildings"))
    for i, building in enumerate(data.get("Buildings")):
        try:
            building["energyStorageCapacityKWH"] = energyStorageCapacityKWH[i]
            building["energyStorageChargeAndDischargeRateKW"] = energyStorageChargeAndDischargeRateKW[i]
            building["batteryModel"] = dropdownBatteryModel[i]
            for buildingComponent in building.get("buildingComponents"):
                if buildingComponent.get("name") == "Solar Generation":
                    buildingComponent["systemSizeKW"] = solarSize[i]
                if buildingComponent.get("name") == "Solar Sample":
                    buildingComponent["multiplicationFactor"] = solarScale[i]
        except:
            pass

    if ctx.triggered_id == "saveconfig-val":
        if saveClicks > 0:
            # files = [('Json Document', '*.json')]
            # file = asksaveasfile(filetypes = files, defaultextension = files)
            # print(file.name)
            with open(generalFile, 'w') as out_file:
                json.dump(data, out_file, sort_keys = True, indent = 4)
        #return data

    if ctx.triggered_id == "loadconfig-val":
        if loadClicks > 0:
            file = filedialog.askopenfile(mode='r', filetypes=[('JSON Files', '*.json')])
        if file:
            filepath = os.path.abspath(file.name)
            with open(filepath, 'r') as data:
                energyStorageCapacityKWH = []
                energyStorageChargeAndDischargeRateKW = []
                dropdownBatteryModel = []
                solarSize= []
                solarScale = []
                simulationRuntime = data["SimulationRuntime"]
                startDateTime = data["StartDateTime"]
                energySellPrice = data["EnergySellPricePerKW"]
                energyBuyPrice = data["EnergyBuyPricePerKW"]
                for i, building in enumerate(data.get("Buildings")):
                    energyStorageCapacityKWH[i] = building["energyStorageCapacityKWH"]
                    energyStorageChargeAndDischargeRateKW[i] = building["energyStorageChargeAndDischargeRateKW"]
                    dropdownBatteryModel[i] = building["batteryModel"]
                    for buildingComponent in building.get("buildingComponents"):
                        if buildingComponent.get("name") == "Solar Generation":
                            solarSize[i] = buildingComponent["systemSizeKW"]
                        if buildingComponent.get("name") == "Solar Sample":
                            solarScale[i] = buildingComponent["multiplicationFactor"]
    
    if ctx.triggered_id == "addLocation-val":
        # Define the path to the directory where you want to save the Excel file
        path_to_directory = os.path.abspath(os.path.dirname(__file__))
        # Define the full path to the Excel file, including the directory and filename
        full_path_to_file = f"{path_to_directory}\excelFiles\{newLocationName}.xlsx"
        if not os.path.isfile(full_path_to_file):
            # Create a new Excel file using the xlsxwriter library
            workbook = xlsxwriter.Workbook(full_path_to_file)
            # Add a worksheet to the Excel file
            worksheet = workbook.add_worksheet()
            # Write some data to the worksheet
            worksheet.write("A1", "Solar Sample")
            worksheet.write("B1", "Day energy use plot")
            # Close the Excel file
            workbook.close()
        configExists = False
        for building in data.get("Buildings"):
            if building.get("name") == newLocationName:
                configExists = True
        if not configExists:
            data.get("Buildings").append({
                "name": newLocationName,
                "energyStorageCapacityKWH": 0,
                "energyStorageChargeAndDischargeRateKW": 5,
                "batteryModel": "Simple",
                "location": [-19.27109880183141, 146.8117881686176],
                "buildingComponents": [
                    {
                        "name": "Solar Sample",
                        "agentType": "ImportAgent",
                        "dataType": "energyProfile",
                        "ConsumptionOrProduction": "production",
                        "minuetsPerDataPoint": 60,
                        "dataTimePeriod": "monthly",
                        "multiplicationFactor": 1,
                        "units": "kw"
        
                    },
                    {
                        "name": "Day energy use plot",
                        "agentType": "ImportAgent",
                        "dataType": "energyProfile",
                        "ConsumptionOrProduction": "consumption",
                        "units": "kw",
                        "dataTimePeriod": "daily",
                        "minuetsPerDataPoint": 30

                    }

                ]
            })
            with open(generalFile, 'w') as out_file:
                json.dump(data, out_file, sort_keys = True, indent = 4)

        pass

    return data, energyStorageCapacityKWH, energyStorageChargeAndDischargeRateKW, dropdownBatteryModel, solarSize, solarScale, startDateTime, simulationRuntime, energySellPrice, energyBuyPrice


if __name__ == '__main__':
    app.run_server(debug=True)