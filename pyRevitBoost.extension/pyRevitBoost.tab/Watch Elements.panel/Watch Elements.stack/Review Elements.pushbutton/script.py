# pylint: disable=import-error
import clr
clr.AddReference('PresentationCore')

import json
from operator import attrgetter
import os

from System import Uri
from System.Windows.Media.Imaging import BitmapImage
from System.Collections.ObjectModel import ObservableCollection
from Autodesk.Revit.DB import (
    BuiltInCategory,
    BuiltInParameter,
    FamilyInstance,
    FilteredElementCollector,
    LocationCurve,
    LocationPoint,
    ModelPathUtils,
    Reference,
    RevitLinkInstance,
    StorageType
)

from pyrevit import forms, script
from boostutils import NotifyPropertyChangedBase, notify_property

__doc__ = '''\
Review watched elements for changes.
'''
__title__ = 'Review Elements'
__author__ = 'Zachary Mathews'


def readDatabase(dbPath):
    try:
        with open(dbPath, 'r') as f:
            db = json.load(f)
    except (IOError, ValueError):
        forms.alert(
            msg='Failed to load database. It might be formatted incorrectly.',
            exitscript=True
        )

    try:
        config = db['config']
        data = db['data']
    except KeyError:
        forms.alert(
            msg='Failed to load database. It might be formatted incorrectly.',
            exitscript=True
        )

    return config, data


class WatchedItem(NotifyPropertyChangedBase):
    def __init__(
        self,
        parameter,
        previousValue,
        value,
        element=None,
        id=None,
        category=None,
        family=None,
        type=None,
    ):
        super(WatchedItem, self).__init__()

        if element:
            self._element = element
            self._id = element.UniqueId
            self._category = element.Category.Name
            self._family = \
                element\
                .get_Parameter(BuiltInParameter.ELEM_FAMILY_PARAM)\
                .AsValueString()
            self._type = \
                element\
                .get_Parameter(BuiltInParameter.ELEM_TYPE_PARAM)\
                .AsValueString()
        else:
            self._element = None
            self._id = id
            self._category = category
            self._family = family
            self._type = type

        self._parameter = parameter
        self._previousValue = previousValue
        self._value = value
        self._needsReconciliation = self._value != self._previousValue

    @property
    def Element(self):
        return self._element

    @property
    def Id(self):
        return self._id

    @property
    def Category(self):
        return self._category

    @property
    def Family(self):
        return self._family

    @property
    def Type(self):
        return self._type

    @property
    def Parameter(self):
        return self._parameter

    @notify_property
    def PreviousValue(self):
        return self._previousValue

    @PreviousValue.setter
    def PreviousValue(self, value):
        self._previousValue = value

    @notify_property
    def NeedsReconciliation(self):
        return self._needsReconciliation

    @NeedsReconciliation.setter
    def NeedsReconciliation(self, value):
        self._needsReconciliation = value

    @property
    def Value(self):
        return self._value


class MonitorForm(forms.WPFWindow):
    def __init__(self, template, dbPath, uidoc, items):
        forms.WPFWindow.__init__(self, template)
        iconUri = Uri(script.get_bundle_file("./icon.png"))
        icon = BitmapImage(iconUri)
        self.Icon = icon

        self._dbPath = dbPath
        self._uidoc = uidoc

        def _sorted(items):
            items = sorted(items, key=attrgetter('Value'))
            items = sorted(items, key=attrgetter('PreviousValue'))
            items = sorted(items, key=attrgetter('Parameter'))
            items = sorted(items, key=attrgetter('Type'))
            items = sorted(items, key=attrgetter('Family'))
            items = sorted(items, key=attrgetter('Category'))
            items = sorted(
                items,
                key=attrgetter('NeedsReconciliation'),
                reverse=True
            )
            return items

        self._items = ObservableCollection[WatchedItem]()
        for item in _sorted(items):
            self._items.Add(item)

        self._table = self.FindName('table')
        self._table.ItemsSource = self._items

        self._reconciled = []

    def show(self):
        self.Show()

    def reconcile(self, sender, *args):
        item = sender.Tag
        item.PreviousValue = item.Value
        item.NeedsReconciliation = False
        self._update_database(item)

        # Resort reconciled item
        oldIdx = self._items.IndexOf(item)
        for newIdx, otherItem in enumerate(self._items):
            if otherItem == item:
                continue

            if otherItem.NeedsReconciliation > item.NeedsReconciliation:
                continue
            elif otherItem.NeedsReconciliation != item.NeedsReconciliation:
                break

            if otherItem.Category < item.Category:
                continue
            elif otherItem.Category != item.Category:
                break

            if otherItem.Family < item.Family:
                continue
            elif otherItem.Family != item.Family:
                break

            if otherItem.Type < item.Type:
                continue
            elif otherItem.Type != item.Type:
                break

            if otherItem.Parameter < item.Parameter:
                continue
            elif otherItem.Parameter != item.Parameter:
                break

            if otherItem.PreviousValue < item.PreviousValue:
                continue
            elif otherItem.PreviousValue != item.PreviousValue:
                break

            if otherItem.Value < item.Value:
                continue
            elif otherItem.Value != item.Value:
                break
        else:
            self._items.Move(oldIdx, newIdx)

        self._items.Move(oldIdx, newIdx - 1)

    def select_in_revit(self, sender, *args):
        el = sender.Tag
        if not el:
            return

        activeView = self._uidoc.ActiveView
        [activeUIView] = [
            uiView for uiView
            in self._uidoc.GetOpenUIViews()
            if uiView.ViewId == activeView.Id
        ]
        bb = el.get_BoundingBox(activeView)
        activeUIView.ZoomAndCenterRectangle(bb.Min, bb.Max)

    def _update_database(self, item):
        _, data = self._read_database()

        data = [
            entry for entry in data
            if entry['id'] != item.Id
            or entry['parameter'] != item.Parameter
        ]

        if item.Element:
            data.append({
                'id': item.Id,
                'category': item.Category,
                'family': item.Family,
                'type': item.Type,
                'parameter': item.Parameter,
                'previous_value': item.PreviousValue
            })

        self._write_database(data)

    def _read_database(self):
        import json

        try:
            with open(self._dbPath, 'r') as f:
                db = json.load(f)
        except (IOError, ValueError):
            forms.alert(
                msg='Failed to load database. '
                    'It might be formatted incorrectly.',
                exitscript=True
            )

        try:
            config = db['config']
            data = db['data']
        except KeyError:
            forms.alert(
                msg='Failed to load database. '
                    'It might be formatted incorrectly.',
                exitscript=True
            )

        return config, data

    def _write_database(self, data):
        import json

        config, _ = self._read_database()

        try:
            with open(self._dbPath, 'w') as f:
                json.dump({
                    'config': config,
                    'data': data
                }, f)
        except IOError:
            forms.alert(
                msg='Failed to write to database.',
                exitscript=True
            )
        except TypeError:
            forms.alert(
                msg='Failed to encode provided data for database.',
                exitscript=True
            )


if __name__ == '__main__':
    uiapp = __revit__   # noqa: F821
    uidoc = uiapp.ActiveUIDocument
    doc = uidoc.Document
    projInfo = doc.ProjectInformation
    selection = uidoc.Selection

    if (doc.IsWorkshared):
        docPath = ModelPathUtils.ConvertModelPathToUserVisiblePath(
            doc.GetWorksharingCentralModelPath())
    else:
        docPath = doc.PathName

    dbDirectory = os.path.dirname(docPath)
    dbDirectory = os.path.join(dbDirectory, 'pyRevitBoost')
    dbPrefix, _ = os.path.splitext(os.path.basename(docPath))
    dbPath = os.path.join(dbDirectory, dbPrefix + '_watch_elements_db.json')

    if not os.path.exists(dbPath):
        forms.alert(
            msg='No elements have been added to watch list yet.',
            exitscript=True
        )

    config, data = readDatabase(dbPath)

    linkInstances = [
        li for li in
        FilteredElementCollector(doc)
        .OfClass(RevitLinkInstance)
        .ToElements()
    ]

    deletedItems = set([item.get('id') for item in data])
    items = []
    for watchRequest in config:
        modelUid = watchRequest.get('model')
        categoryEnum = watchRequest.get('category')
        familyUid = watchRequest.get('family')
        parameterName = watchRequest.get('parameter')

        model = doc.GetElement(modelUid)
        linkDoc = model.GetLinkDocument()
        elements = [
            e for e in
            FilteredElementCollector(linkDoc)
            .OfClass(FamilyInstance)
            .OfCategory(getattr(BuiltInCategory, categoryEnum))
            .ToElements()
            if not familyUid or e.Symbol.Family.UniqueId == familyUid
        ]

        for e in elements:
            item = [
                item for item in data
                if item.get('id') == e.UniqueId
                and item.get('parameter') == parameterName
            ]

            previousValue = ''
            if item:
                item = item[0]
                previousValue = item.get('previous_value')

            # Location is handled differently
            if parameterName == 'Location':
                location = e.Location
                if type(location) == LocationPoint:
                    value = location.Point.ToString()
                elif type(location) == LocationCurve:
                    value = str([
                        location.Curve.Evaluate(0.0, False).ToString(),
                        location.Curve.Evaluate(0.2, False).ToString(),
                        location.Curve.Evaluate(0.4, False).ToString(),
                        location.Curve.Evaluate(0.5, False).ToString(),
                        location.Curve.Evaluate(0.6, False).ToString(),
                        location.Curve.Evaluate(0.8, False).ToString(),
                        location.Curve.Evaluate(1.0, False).ToString()
                    ])

                items.append(WatchedItem(
                    element=e,
                    parameter=parameterName,
                    previousValue=previousValue,
                    value=value
                ))
            else:
                parameter = e.LookupParameter(parameterName)
                if not parameter:
                    parameter = e.Symbol.LookupParameter(parameterName)

                if (
                    not parameter
                    or parameter.StorageType == getattr(StorageType, 'None')
                ):
                    value = ''
                elif parameter.StorageType == StorageType.String:
                    value = parameter.AsString()
                elif parameter.StorageType == StorageType.Integer:
                    value = str(parameter.AsInteger())
                elif parameter.StorageType == StorageType.Double:
                    value = str(parameter.AsDouble())
                elif parameter.StorageType == StorageType.ElementId:
                    element = linkDoc.GetElement(parameter.AsElementId())
                    ref = Reference(element)
                    value = ref.ConvertToStableRepresentation(linkDoc)

                items.append(WatchedItem(
                    element=e,
                    parameter=parameterName,
                    previousValue=previousValue,
                    value=value
                ))

            if item:
                deletedItems.discard(item.get('id'))

    for itemId in deletedItems:
        # This will only find the first matched parameter
        # if multiple parameters are watched. It shouldn't
        # matter, since the element was deleted anyways.
        item = next(
            item for item in data
            if item.get('id') == itemId
        )
        items.append(WatchedItem(
            id=item.get('id'),
            category=item.get('category'),
            family=item.get('family'),
            type=item.get('type'),
            parameter=item.get('parameter'),
            previous_value=item.get('previous_value'),
            value='[[ DELETED ]]' 
        ))

    # Show form
    MonitorForm(
        template='form.xaml',
        dbPath=dbPath,
        uidoc=uidoc,
        items=items
    ).show()
