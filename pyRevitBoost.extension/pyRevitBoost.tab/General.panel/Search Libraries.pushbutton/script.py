# pylint: disable=import-error
import clr
clr.AddReference('System.ObjectModel')
from System.Collections.ObjectModel import ObservableCollection

clr.AddReference('System.Collections')
from System.Collections.Generic import List

import os
import sys
import re
import codecs
import json
from itertools import groupby

from Autodesk.Revit.DB import Element, ElementId, ElementTransformUtils, SketchPlane
from Autodesk.Revit.Exceptions import (ArgumentException,
                                       InvalidOperationException)

import rpw
from pyrevit import forms, script

__doc__ = '''\
Find a family type or view in the libraries and insert it into the document.
'''
__title__ = 'Search\nLibraries'
__author__ = 'Zachary Mathews'


class TrieNode:
    def __init__(self):
        self.children = [None] * (26 + 10 + 2)
        self.terminal_items = set()
        self.items = set()


class Trie:
    def __init__(self):
        self.root = self.create_node()

    def create_node(self):
        return TrieNode()

    def _char_to_index(self, ch):
        if ch.isalpha():
            return ord(ch) - ord('a')
        elif ch.isdigit():
            return ord(ch) - ord('0') + 26
        elif ch == '.':
            return 36
        elif ch == ',':
            return 37
        else:
            return None

    def insert(self, key, item):
        p_crawl = self.root
        p_crawl.items.add(item)

        # Remove the first character
        key = list(key)
        key.pop(0)

        for char in key:
            index = self._char_to_index(char)
            if not index:
                continue    # skip any character we don't have an index for
            elif not p_crawl.children[index]:
                p_crawl.children[index] = self.create_node()
                p_crawl = p_crawl.children[index]
            else:
                p_crawl = p_crawl.children[index]

            p_crawl.items.add(item)

        p_crawl.terminal_items.add(item)

    def search(self, key):
        p_crawl = self.root
        for item in p_crawl.items:
            item.score += 1

        # Remove the first character
        key = list(key)
        key.pop(0)

        # Add a point to each item for each additional character in one
        # of its keywords that matches the search term
        for char in key:
            index = self._char_to_index(char)
            if not index:
                continue    # skip any character we don't have an index for
            elif not p_crawl.children[index]:
                break
            else:
                p_crawl = p_crawl.children[index]
                for item in p_crawl.items:
                    item.score += 1

        else:
            # Add an extra 2 points to each item with the whole search term
            # in its keywords list
            for item in p_crawl.terminal_items:
                item.score += 2


class ScoredTemplateListItem(forms.TemplateListItem):
    def __init__(self, *args, **kwargs):
        super(ScoredTemplateListItem, self).__init__(*args, **kwargs)
        self._score = 0

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, score):
        self._score = score


class FuzzySelectFromList(forms.SelectFromList):
    def __init__(self, *args, **kwargs):
        super(FuzzySelectFromList, self).__init__(*args, **kwargs)

        self.index = dict()
        for item in self._get_active_ctx():
            for term in self._extract_terms(item.name):
                if not term[0] in self.index.keys():
                    self.index[term[0]] = Trie()

                self.index[term[0]].insert(term, item)

    @staticmethod
    def _extract_terms(phrase):
        terms = set()
        for t in re.split(r'[-,_,\W]', phrase.lower()):
            if t:
                terms.add(t)

        return terms

    # Override
    def search_txt_changed(self, sender, args):
        '''Handle text change in search box.'''
        if self.search_tb.Text == '':
            self.hide_element(self.clrsearch_b)
        else:
            self.show_element(self.clrsearch_b)

        self._search = self.search_tb.Text
        if self._search:
            self._compute_scores()
            self._list_options(option_filter=self.search_tb.Text)

    # Override
    def _list_options(self, option_filter=None):
        self.checkall_b.Content = 'Check'
        self.uncheckall_b.Content = 'Uncheck'
        self.toggleall_b.Content = 'Toggle'

        # Display top 20 matches
        items = set(self._get_active_ctx())
        top_matches = []
        while items and len(top_matches) < 20:
            top_match = max(items, key=lambda item: item.score)
            top_matches.append(top_match)
            items.remove(top_match)

        self.list_lb.ItemsSource = \
            ObservableCollection[forms.TemplateListItem](
                [m for m in top_matches]
            )

    def _compute_scores(self):
        for item in self._get_active_ctx():
            item.score = 0

        search_terms = self._extract_terms(self._search)
        for term in search_terms:
            if term[0] in self.index.keys():
                self.index[term[0]].search(term)


def _insert_view(db):
    class View(object):
        def __init__(self, path, name):
            self._path = path
            self._name = name

        @property
        def name(self):
            return self._name

        @property
        def path(self):
            return self._path

    class ViewOption(ScoredTemplateListItem):
        @property
        def name(self):
            return '{}'.format(self.item.name)

    views = []
    for path, _views in db["views"].items():
        for view in _views:
            views.append(View(path=path, name=view))

    options = []
    for view in views:
        options.append(ViewOption(view))

    res = FuzzySelectFromList.show(
        context=options,
        multiselect=True,
        height=650,
        width=750
    )

    if not res:
        sys.exit()

    succeeded = []
    failed = []
    for path, views in groupby(res, key=lambda view: view.path):
        doc = rpw.revit.doc
        try:
            other_doc = \
                rpw.revit.app.OpenDocumentFile(path)
        except:
            failed.extend([v.name for v in views])
        else:
            other_doc_views = rpw.db.Collector(
                doc=other_doc,
                of_category='OST_Views'
            ).get_elements(wrapped=False)

            view_names = set([v.name for v in views])
            views_to_copy = [
                v for v in other_doc_views if v.Name in view_names
            ]

            for view in views_to_copy:
                try:
                    with rpw.db.Transaction('Copy View'):
                        [copied_view_id] = ElementTransformUtils.CopyElements(
                            other_doc,
                            List[ElementId]([view.Id]),
                            doc,
                            None,
                            None
                        )
                    with rpw.db.Transaction('Copy Elements from View'):
                        elements_to_copy = rpw.db.Collector(
                            doc=other_doc,
                            owner_view=view,
                            where=lambda e: type(e.unwrap()) is not Element
                        ).get_elements(wrapped=False)
                        ElementTransformUtils.CopyElements(
                            view,
                            List[ElementId]([e.Id for e in elements_to_copy]),
                            doc.GetElement(copied_view_id),
                            None,
                            None
                        )
                except (ArgumentException, InvalidOperationException) as e:
                    failed.append(view.Name)
                else:
                    view_names.remove(view.Name)
                    succeeded.append(view.Name)

            failed.extend(view_names)
            other_doc.Close(False)

    if failed:
        forms.alert(
            msg='Successfully loaded the following views:\n{}\n\n'
                'Failed to load the following views:\n{}'.format(
                    '\n'.join(succeeded),
                    '\n'.join(failed)
                ),
            exitscript=True
        )


def _insert_family_type(db):
    class FamilyType(object):
        def __init__(self, path, name):
            self._path = path
            self._family = os.path.splitext(path)[0].split('\\')[-1]
            self._name = name

        @property
        def path(self):
            return self._path

        @property
        def family(self):
            return self._family

        @property
        def name(self):
            return self._name

    class FamilyTypeOption(ScoredTemplateListItem):
        @property
        def name(self):
            return '{} : {}'.format(self.item.family, self.item.name)

    family_types = []
    for path, _family_types in db["family_types"].items():
        for family_type in _family_types:
            family_types.append(FamilyType(path=path, name=family_type))

    options = []
    for family_type in family_types:
        options.append(FamilyTypeOption(family_type))

    res = FuzzySelectFromList.show(
        context=options,
        multiselect=True,
        height=650,
        width=750
    )

    if not res:
        sys.exit()

    succeeded = []
    failed = []
    for ft in res:
        with rpw.db.Transaction(
            doc=rpw.revit.doc,
            name='Load family type {}'.format(ft.name)
        ):
            if rpw.revit.doc.LoadFamilySymbol(ft.path, ft.name):
                succeeded.append(ft.name)
            else:
                failed.append(ft.name)

    if failed:
        forms.alert(
            msg='Successfully loaded the following family types:\n{}\n\n'
                'Failed to load the following family types:\n{}'.format(
                    '\n'.join(succeeded),
                    '\n'.join(failed)
                ),
            exitscript=True
        )


def _index_libraries():
    def _is_new(file, last_updated):
        return os.path.getctime(file) > last_updated

    def _is_updated(file, last_updated):
        return os.path.getmtime(file) > last_updated

    def _is_not_old(filename):
        old_regex = r'^.+\.old$'
        return not re.match(old_regex, filename)

    def _is_not_revision(filename):
        revision_regex = r'^.+\.[0-9]{4,}$'
        return not re.match(revision_regex, filename)

    app = rpw.revit.app
    libraries_db = script.get_data_file('boost_libraries_db', 'json')
    last_updated = None
    if os.path.isfile(libraries_db):
        last_updated = os.path.getmtime(libraries_db)
        libraries = _get_libraries()

        if 'paths' not in libraries.keys():
            libraries['paths'] = {}
        if 'views' not in libraries.keys():
            libraries['views'] = {}
        if 'family_types' not in libraries.keys():
            libraries['family_types'] = {}
    else:
        user_wishes_to_proceed = forms.alert(
            msg='This might take a while. Are you sure you want to continue?',
            ok=False,
            yes=True,
            no=True
        )
        if not user_wishes_to_proceed:
            sys.exit()

        libraries = {}
        libraries['paths'] = {}
        libraries['views'] = {}
        libraries['family_types'] = {}

    libs = [lib.Value for lib in app.GetLibraryPaths()]
    rvts = []
    rfas = []
    for lib in libs:
        for root, _, files in os.walk(lib):
            for file in files:
                filename, file_ext = os.path.splitext(file)

                if (
                    _is_not_revision(filename)
                    and _is_not_old(filename)
                    and (
                        lib not in libraries['paths']
                        or _is_new(os.path.join(root, file), last_updated)
                        or _is_updated(os.path.join(root, file), last_updated)
                        or last_updated is None
                    )
                ):
                    if file_ext == '.rvt':
                        rvts.append(os.path.join(root, file))
                    elif file_ext == '.rfa':
                        rfas.append(os.path.join(root, file))

    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        count = 0
        total = len(rvts) + len(rfas)

        # Remove files that are no longer part of the library directories
        # from the index
        old_views_by_rvt = libraries['views']
        for rvt in old_views_by_rvt.keys():
            if (
                not os.path.isfile(rvt)
                or not any([
                    rvt.startswith(path) for path in libraries['paths']
                ])
            ):
                del libraries['views'][rvt]

        old_family_types_by_rfa = libraries['family_types']
        for rfa in old_family_types_by_rfa.keys():
            if (
                not os.path.isfile(rfa)
                or not any([
                    rfa.startswith(path) for path in libraries['paths']
                ])
            ):
                del libraries['family_types'][rfa]

        # Gather information on changed rvt files
        views_by_rvt = {}
        for rvt in rvts:
            if pb.cancelled:
                sys.exit()

            def _extract_views(doc):
                return rpw.db.Collector(
                    doc=doc,
                    of_category='OST_Views'
                )

            if rvt == rpw.revit.doc.PathName:
                doc = rpw.revit.doc
            else:
                try:
                    doc = app.OpenDocumentFile(rvt)
                except:
                    pass
                else:
                    views_by_rvt[rvt] = [v.Name for v in _extract_views(doc)]
                    doc.Close(False)

            count += 1
            pb.update_progress(count, total)

        # Gather information on changed rfa files
        family_types_by_rfa = {}
        for rfa in rfas:
            if pb.cancelled:
                sys.exit()

            def _extract_family_types(doc):
                fm = doc.FamilyManager
                return [t.Name for t in fm.Types]

            if rfa == rpw.revit.doc.PathName:
                doc = rpw.revit.doc
                family_types_by_rfa[rfa] = _extract_family_types(doc)
            else:
                try:
                    doc = app.OpenDocumentFile(rfa)
                except:
                    pass
                else:
                    family_types_by_rfa[rfa] = _extract_family_types(doc)
                    doc.Close(False)

            count += 1
            pb.update_progress(count, total)

        # Update library with new information
        libraries['paths'] = libs
        libraries['views'].update(views_by_rvt)
        libraries['family_types'].update(family_types_by_rfa)

        # Write library index to file
        data = json.dumps({
            "paths": libraries["paths"],
            "views": libraries['views'],
            "family_types": libraries['family_types']
        }, ensure_ascii=False).encode('utf-8')
        with open(libraries_db, 'w+') as f:
            f.write(data)


def _get_libraries():
    libraries_db = script.get_data_file('boost_libraries_db', 'json')
    if not os.path.isfile(libraries_db):
        forms.alert(
            msg='Sorry! It appears that your Revit libraries have not been '
                'indexed yet. '
                'Please ensure that your Revit library paths are properly '
                'configured, and then choose Index Libraries to index the '
                'libraries.',
            ok=False,
            cancel=True,
            exitscript=True
        )

    with open(libraries_db, 'r') as f:
        utf8_reader = codecs.getreader('utf-8')
        libraries_s = utf8_reader(f).read()
        libraries = json.loads(libraries_s)

    return libraries


if __name__ == '__main__':
    cmd = forms.CommandSwitchWindow.show(
        context=['Insert View', 'Insert Family Type', 'Index Libraries']
    )

    if cmd == 'Insert View':
        libraries = _get_libraries()
        _insert_view(libraries)
    elif cmd == 'Insert Family Type':
        libraries = _get_libraries()
        _insert_family_type(libraries)
    elif cmd == 'Index Libraries':
        _index_libraries()
