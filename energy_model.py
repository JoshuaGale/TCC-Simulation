from locale import currency
import mesa
import math
from datetime import datetime
from datetime import timedelta
import pandas as pd
###
# Possible agent types include Batteries, Solar, building energy use
#
#
#
#
###

class BuildingAgent(mesa.Agent):
    """A building that is made up of consumption production and storage and tries to satisfy its community."""

    def __init__(self, unique_id, model, config):
        super().__init__(unique_id, model)
        self.name = config.get("name")
        self.energyConsumption = 0
        self.energyProduction = 0
        self.energyStorageCapacity = config.get("energyStorageCapacityKWH") * 1000 * 60
        self.energyStorageUtilized = 0
        self.energyStorageChargeAndDischargeRate = config.get("energyStorageChargeAndDischargeRateKW") * 1000
        self.outsideTemperature = 0
        self.componentExecutionStage = 0
        self.totalEnergyLocalNetworkContribution = 0
        self.currentStep = 0
        self.amountToChargeOrDischarge = 0
        self.batteryModel = config.get("batteryModel")
        self.location = config.get("location")
        self.model = model
        self.schedule = mesa.time.RandomActivation(self)
        if config.get("buildingComponents"):
            for buildingComponent in config.get("buildingComponents"):
                self.model.idCount += 1
                if buildingComponent["agentType"] == "GenericEnergyAgent":
                    self.schedule.add(GenericEnergyAgent(self.model.idCount, self, buildingComponent))
                elif buildingComponent["agentType"] == "SolarAgent":
                    self.schedule.add(SolarAgent(self.model.idCount, self, buildingComponent))
                elif buildingComponent["agentType"] == "ImportAgent":
                    self.schedule.add(ImportAgent(self.model.idCount, self, buildingComponent))


    def step(self):
        if self.model.stepStage == 0:
            self.currentStep += 1
            self.energyConsumption = 0
            self.energyProduction = 0
            ### Execute Building Components
            self.componentExecutionStage = 0
            self.schedule.step()


            ### Energy Sharing, add to net of the network
            self.model.stepEnergyLevel += self.energyProduction - self.energyConsumption
            self.totalEnergyLocalNetworkContribution += self.energyProduction - self.energyConsumption

        ### Energy Battery Storage Management after net power level is decided
        elif self.model.stepStage == 1:
            if self.batteryModel == "Simple":
                maxDischarge = 0
                maxCharge = 0
                if self.energyStorageUtilized >= self.energyStorageChargeAndDischargeRate:
                    maxDischarge = self.energyStorageChargeAndDischargeRate
                else: 
                    maxDischarge = self.energyStorageUtilized
                if self.energyStorageCapacity - self.energyStorageUtilized >= self.energyStorageChargeAndDischargeRate:
                    maxCharge = self.energyStorageChargeAndDischargeRate
                else:
                    maxCharge = self.energyStorageCapacity - self.energyStorageUtilized

                self.amountToChargeOrDischarge = max(min(maxCharge, self.model.stepEnergyLevel), -maxDischarge)
                self.model.stepEnergyLevel -= self.amountToChargeOrDischarge
                self.energyStorageUtilized += self.amountToChargeOrDischarge

            # keeps a minimum amount of power in batteries for emergencies
            if self.batteryModel == "Complex":
                emergencyRetentionLevel = 0.5
                maxDischarge = 0
                maxCharge = 0

                if self.energyStorageUtilized >= self.energyStorageChargeAndDischargeRate:
                    maxDischarge = self.energyStorageChargeAndDischargeRate
                else: 
                    maxDischarge = self.energyStorageUtilized 
                if self.energyStorageUtilized - maxDischarge <= emergencyRetentionLevel * self.energyStorageCapacity and self.energyStorageUtilized >= emergencyRetentionLevel * self.energyStorageCapacity:
                    maxDischarge = self.energyStorageUtilized - (emergencyRetentionLevel * self.energyStorageCapacity)

                if self.energyStorageCapacity - self.energyStorageUtilized >= self.energyStorageChargeAndDischargeRate:
                    maxCharge = self.energyStorageChargeAndDischargeRate
                else:
                    maxCharge = self.energyStorageCapacity - self.energyStorageUtilized

                self.amountToChargeOrDischarge = max(min(maxCharge, self.model.stepEnergyLevel), -maxDischarge)
                self.model.stepEnergyLevel -= self.amountToChargeOrDischarge
                self.energyStorageUtilized += self.amountToChargeOrDischarge
                



class GenericEnergyAgent(mesa.Agent):
    """An agent that uses or produces energy."""

    def __init__(self, unique_id, model, config):
        super().__init__(unique_id, model)
        self.energyUse = 0
        self.currentStep = 0
        self.energyModel = config["model"]
        self.generationOrConsumption = config["generationOrConsumption"]
        self.timeRange = config["timeRange"]

    def step(self):
        if self.model.componentExecutionStage == 0:
            self.currentStep += 1
            exec(self.energyModel)
            if self.timeRange:
                if self.currentStep < self.timeRange[0] or self.currentStep > self.timeRange[1]:
                    self.energyUse = 0
            if self.generationOrConsumption == "generation":
                self.model.energyProduction += self.energyUse
            elif self.generationOrConsumption == "consumption":
                self.model.energyConsumption += self.energyUse


class SolarAgent(mesa.Agent):
    """OUTDATED - An agent that generates energy."""

    def __init__(self, unique_id, model, config):
        super().__init__(unique_id, model)
        self.energyUse = 0
        self.currentStep = 0
        self.systemSizeKW = config["systemSizeKW"]

    def step(self):
        if self.model.componentExecutionStage == 0:
            self.currentStep += 1
            
            day = math.floor((self.currentStep - 1) / 1440)
            
            equation = ((200000)/(100 * math.sqrt(2 * math.pi)) * math.e ** -((((self.currentStep - (725 + (day * 1440))) ** 2) / (2 * (100 ** 2)))))
            self.energyUse = equation * self.systemSizeKW
            self.model.energyProduction += self.energyUse


class ImportAgent(mesa.Agent):
    """An Agent that Imports a list of values from the config"""
    def __init__(self, unique_id, model, config):
        super().__init__(unique_id, model)
        self.energyUse = 0
        self.currentStep = 0
        lists = {}
        df = pd.read_excel(self.model.model.excelDirectory + "\\" + self.model.name + ".xlsx")
        for index, column in enumerate(df.columns):
            lists[column] = []
            for value in df.values:
                if not math.isnan(value[index]): 
                    lists[column].append(value[index])

        self.inputData = lists.get(config.get("name"))
        self.dataType = config["dataType"]
        self.dataTimePeriod = config.get("dataTimePeriod")
        self.minuetsPerDataPoint = config["minuetsPerDataPoint"]
        self.timeSolarReference = {}
        self.ConsumptionOrProduction = config.get("ConsumptionOrProduction")
        self.multiplicationFactor = config.get("multiplicationFactor")
        if self.multiplicationFactor == None:
            self.multiplicationFactor = 1
        self.currentStepValue = 0
        self.unit = config.get("units")
        if self.dataType == "energyProfile":
            startDate = datetime(self.model.model.startDate.year,1,1,0,0)
            if self.dataTimePeriod == "monthly":
                while (startDate.month != 12 or startDate.day != 31):
                    self.timeSolarReference[startDate.strftime("%m-%d-%H-%M")] = self.inputData[(startDate.hour * int(60 / self.minuetsPerDataPoint)) + int(startDate.minute / self.minuetsPerDataPoint) + ((startDate.month - 1) * 24 * int(60 / self.minuetsPerDataPoint))] * self.multiplicationFactor
                    startDate = startDate + timedelta(minutes=self.minuetsPerDataPoint)
            elif self.dataTimePeriod == "daily":
                for dataPoint in self.inputData:
                    self.timeSolarReference[startDate.strftime("%H-%M")] = dataPoint * self.multiplicationFactor


                    startDate = startDate + timedelta(minutes=self.minuetsPerDataPoint)



    def step(self):
        if self.model.componentExecutionStage == 0:
            self.currentStep += 1

            if self.dataType == "energyProfile":
                currentDateTime = self.model.model.startDate + timedelta(minutes=float(self.currentStep))
                if self.dataTimePeriod == "monthly":
                    retrievedValue = self.timeSolarReference.get(currentDateTime.strftime("%m-%d-%H-%M"))
                elif self.dataTimePeriod == "daily": 
                    retrievedValue = self.timeSolarReference.get(currentDateTime.strftime("%H-%M"))

                if (retrievedValue != None):
                    if self.unit == "kw":
                        self.currentStepValue = retrievedValue * 1000
                    else:
                        self.currentStepValue = retrievedValue
                if self.ConsumptionOrProduction == "production":
                    self.model.energyProduction += self.currentStepValue
                elif self.ConsumptionOrProduction == "consumption":
                    self.model.energyConsumption += self.currentStepValue

            inputValue = 0

            if self.currentStep - 1 <= len(self.inputData) * self.minuetsPerDataPoint:
                inputValue = self.inputData[math.ceil((self.currentStep - 1) / self.minuetsPerDataPoint)-1]

            if self.dataType == "EnergyConsumption":
                self.model.energyConsumption += inputValue * 1000
            
            if self.dataType == "EnergyProduction":
                self.model.energyProduction += inputValue * 1000
            
            if self.dataType == "OutsideTemperature":
                self.model.outsideTemperature = inputValue


class EnergyModel(mesa.Model):
    """A top level model that holds the building agents"""

    def __init__(self, config):
        self.stepEnergyLevel = 0
        self.stepStage = 0
        self.idCount = 0
        self.schedule = mesa.time.RandomActivation(self)
        self.startDate = config['StartDateTime']
        self.excelDirectory = config.get("excelDirectory")
        ### Create agents
        for building in config['Buildings']:
            self.idCount += 1
            b = BuildingAgent(self.idCount, self, building)
            self.schedule.add(b)

    def step(self):
        """Advance the model by one step."""
        self.stepEnergyLevel = 0
        self.stepStage = 0
        self.schedule.step()
        self.stepStage = 1
        self.schedule.step()

