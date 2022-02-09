# pylint: disable=import-error
import sys
import os
import json

from Autodesk.Revit.DB import (
    BuiltInCategory,
    Category,
    FamilyInstance,
    FilteredElementCollector,
    ModelPathUtils,
    RevitLinkInstance
)

from pyrevit import forms

__doc__ = '''\
Add elements to watch for changes.
'''
__title__ = 'Add Elements'
__author__ = 'Zachary Mathews'


class AddForm(forms.WPFWindow):
    def __init__(self, template, doc):
        forms.WPFWindow.__init__(self, template)
        self._doc = doc
        self._added = []

        self._modelComboBox = self.FindName('modelComboBox')
        self._categoryComboBox = self.FindName('categoryComboBox')
        self._familyComboBox = self.FindName('familyComboBox')
        self._parameterComboBox = self.FindName('parameterComboBox')

        collector = FilteredElementCollector(doc)
        links = collector.OfClass(RevitLinkInstance).ToElements()
        self._modelsMap = dict()
        for m in links:
            if not m.GetLinkDocument():
                continue
            self._modelsMap[m.GetLinkDocument().Title] = m.UniqueId

        supportedCategoryNames = [
            'OST_DuctTerminal',
            'OST_CableTrayFitting',
            'OST_Casework',
            'OST_Columns',
            'OST_CommunicationDevices',
            'OST_ConduitFitting',
            'OST_DataDevices',
            'OST_Doors',
            'OST_DuctAccessory',
            'OST_DuctFitting',
            'OST_ElectricalEquipment',
            'OST_ElectricalFixtures',
            'OST_Entourage',
            'OST_FireAlarmDevices',
            'OST_Furniture',
            'OST_GenericModel',
            'OST_LightingDevices',
            'OST_LightingFixtures',
            'OST_Mass',
            'OST_MechanicalEquipment',
            'OST_NurseCallDevices',
            'OST_Parking',
            'OST_PipeAccessory',
            'OST_PipeFitting',
            'OST_Planting',
            'OST_PlumbingFixtures',
            'OST_SecurityDevices',
            'OST_Site',
            'OST_SpecialityEquipment',
            'OST_Sprinklers',
            'OST_StructuralColumns',
            'OST_StructConnections',
            'OST_StructuralFoundation',
            'OST_StructuralFraming',
            'OST_StructuralStiffener',
            'OST_TelephoneDevices',
            'OST_Windows'
        ]

        self._categoriesMap = dict()
        for modelName, modelUid in self._modelsMap.items():
            model = doc.GetElement(modelUid).GetLinkDocument()

            self._categoriesMap[modelName] = dict()

            supportedCategoryEnumMap = dict([
                (
                    Category.GetCategory(
                        model,
                        getattr(BuiltInCategory, cn)
                    ).Id,
                    cn
                )
                for cn in supportedCategoryNames
            ])

            familyInstances = \
                FilteredElementCollector(model)\
                .OfClass(FamilyInstance)\
                .ToElements()

            placedSupportedCategoryIds = set([
                fi.Category.Id for fi in familyInstances
                if fi.Category.Id in supportedCategoryEnumMap.keys()
            ])

            for categoryId in placedSupportedCategoryIds:
                category = Category.GetCategory(model, categoryId)
                categoryEnum = supportedCategoryEnumMap[categoryId]
                self._categoriesMap[modelName][category.Name] = categoryEnum

        self._familiesMap = dict()
        for modelName, modelUid in self._modelsMap.items():
            model = doc.GetElement(modelUid).GetLinkDocument()

            self._familiesMap[modelName] = dict()

            for categoryName, categoryEnum in self._categoriesMap[modelName].items():
                category = \
                    Category.GetCategory(
                        model,
                        getattr(BuiltInCategory, categoryEnum)
                    )

                self._familiesMap[modelName][categoryName] = dict()

                familyInstances = \
                    FilteredElementCollector(model)\
                    .OfCategoryId(category.Id)\
                    .OfClass(FamilyInstance)\
                    .ToElements()

                placedFamilyIds = \
                    set([fi.Symbol.Family.Id for fi in familyInstances])

                for fid in placedFamilyIds:
                    family = model.GetElement(fid)
                    self._familiesMap[modelName][categoryName][family.Name] = \
                        family.UniqueId

        self._parametersMap = dict()
        for modelName, modelUid in self._modelsMap.items():
            model = doc.GetElement(modelUid).GetLinkDocument()

            self._parametersMap[modelName] = dict()

            familyInstances = \
                FilteredElementCollector(model)\
                .OfClass(FamilyInstance)\
                .ToElements()

            for categoryName, families in self._familiesMap[modelName].items():
                self._parametersMap[modelName][categoryName] = dict()

                for familyName, familyUid in families.items():
                    # Find an instance to collect all possible parameters
                    instance = next(
                        fi for fi in familyInstances
                        if fi.Symbol.Family.UniqueId == familyUid
                    )

                    instanceParams = [
                        p for p
                        in instance.Parameters
                    ]
                    typeParams = [
                        p for p
                        in instance.Symbol.Parameters
                    ]
                    familyParams = [
                        p for p
                        in instance.Symbol.Family.Parameters
                    ]

                    params = []
                    params.extend(instanceParams)
                    params.extend(typeParams)
                    params.extend(familyParams)

                    self._parametersMap[modelName][categoryName][familyName] \
                        = [p.Definition.Name for p in params]
                    self._parametersMap[modelName][categoryName][familyName] \
                        .append('Location')

        self._selectedModel = None
        self._selectedCategory = None
        self._selectedFamily = None
        self._selectedParameter = None

        self.rebind()

    @property
    def models(self):
        return sorted(self._modelsMap.keys())

    @property
    def categories(self):
        return sorted(
            self._categoriesMap
                .get(self._selectedModel)
                .keys()
        )

    @property
    def families(self):
        return sorted(
            self._familiesMap
                .get(self._selectedModel)
                .get(self._selectedCategory)
                .keys()
        )

    @property
    def parameters(self):
        def _extractNestedValues(d):
            if type(d) is list:
                return set(d)

            out = set()
            for v in d.values():
                out.update(_extractNestedValues(v))

            return out

        if not self._selectedModel:
            return []

        paramsMap = self._parametersMap.get(self._selectedModel)

        # Category and family are optional
        if self._selectedCategory:
            paramsMap = paramsMap.get(self._selectedCategory)

        if self._selectedFamily:
            paramsMap = paramsMap.get(self._selectedFamily)

        return sorted(list(_extractNestedValues(paramsMap)))

    def changeSelectedModel(self, sender, args):
        self._selectedModel = sender.SelectedItem
        self._selectedCategory = None
        self._selectedFamily = None
        self._selectedParameter = None
        self.rebind()

    def changeSelectedCategory(self, sender, args):
        self._selectedCategory = sender.SelectedItem
        self._selectedFamily = None
        self.rebind()

    def changeSelectedFamily(self, sender, args):
        self._selectedFamily = sender.SelectedItem
        self.rebind()

    def watch(self, sender, args):
        self._selectedParameter = self._parameterComboBox.SelectedItem
        if not self._selectedParameter:
            return

        selectedModelUid = self._modelsMap[self._selectedModel]
        selectedParameterName = self._selectedParameter
        add = {
            'model': selectedModelUid,
            'parameter': selectedParameterName
        }

        # Category and family are optional
        if self._selectedCategory:
            selectedCategoryEnum = self._categoriesMap[self._selectedModel][self._selectedCategory]
            add['category'] = selectedCategoryEnum

        if self._selectedFamily:
            selectedFamilyUid = self._familiesMap[self._selectedModel][self._selectedCategory][self._selectedFamily]
            add['family'] = selectedFamilyUid

        self._added.append(add)

        self._modelComboBox.SelectedItem = None
        self._categoryComboBox.SelectedItem = None
        self._familyComboBox.SelectedItem = None
        self._parameterComboBox.SelectedItem = None
        self.rebind()

    def rebind(self):
        self._modelComboBox.ItemsSource = self.models

        if self._selectedModel:
            self._categoryComboBox.ItemsSource = self.categories

        if self._selectedCategory:
            self._familyComboBox.ItemsSource = self.families

        self._parameterComboBox.ItemsSource = self.parameters

    def showDialog(self):
        self.ShowDialog()
        return self._added


if __name__ == '__main__':
    uiapp = __revit__   # noqa: F821
    app = uiapp.Application
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document

    if (doc.IsWorkshared):
        docPath = ModelPathUtils.ConvertModelPathToUserVisiblePath(
            doc.GetWorksharingCentralModelPath())
    else:
        docPath = doc.PathName

    dbDirectory = os.path.dirname(docPath)
    dbDirectory = os.path.join(dbDirectory, 'pyRevitBoost')
    dbPrefix, _ = os.path.splitext(os.path.basename(docPath))
    dbPath = os.path.join(dbDirectory, dbPrefix + '_watch_elements_db.json')

    try:
        with open(dbPath, 'r') as f:
            db = json.load(f)
    except (IOError, ValueError):
        db = {
            'config': [],
            'data': []
        }

    added = AddForm(
        template='form.xaml',
        doc=doc
    ).showDialog()
    for item in added:
        db['config'].append(item)

    if not added:
        sys.exit()

    if not os.path.exists(dbDirectory):
        os.makedirs(dbDirectory)

    with open(dbPath, 'w+') as f:
        json.dump(db, f)
