from wikidataStuff.WikidataStuff import WikidataStuff as WDS
import pywikibot
import importer_utils as utils
from os import path

MAPPING_DIR = "data"
PROPS = utils.load_json(path.join(MAPPING_DIR, "properties.json"))


class Uploader(object):

    TEST_ITEM = "Q4115189"

    def make_labels(self):
        labels = self.data["labels"]
        new_labels = []
        for item in labels:
            new_labels.append({'language': item, 'value': labels[item]})
        return new_labels

    def make_aliases(self):
        aliases = self.data["aliases"]
        new_aliases = []
        for item in aliases:
            language = item
            for value in aliases[language]:
                new_alias = {"language": language, "value": value}
                new_aliases.append(new_alias)
        return new_aliases

    def add_labels(self, target_item, labels, aliases, log):
        """
        Add labels and aliases.

        Normally, if the WD item already has a label in $lang
        and the data object has another one, the new one
        will be automatically added as an alias. Otherwise
        (no existing label), it will be added as a label.
        However, the data model supports an optional [aliases]
        field as well.
        Its contents will be added directly as an alias, without checking
        if it could be a label first.
        """
        print(labels)
        for label in labels:
            target_item.get()
            label_content = label['value']
            language = label['language']
            self.wdstuff.addLabelOrAlias(
                language, label_content, target_item)
            if log:
                t_id = target_item.getID()
                message = "{} ADDED LABEL {} {}".format(
                    t_id, language, label_content)
                log.logit(message)
        for alias in aliases:
            target_item.get()
            name = alias["value"]
            language = alias["language"]
            t_aliases = target_item.aliases
            if language in t_aliases and name in t_aliases[language]:
                return
            else:
                summary = "Added [{}] alias to [[{}]], {}".format(
                    language, target_item.title(), self.summary)
                target_item.editAliases(
                    {language: [name]}, summary=summary)
            if log:
                t_id = target_item.getID()
                message = "{} ADDED ALIAS {} {}".format(
                    t_id, language, name)
                log.logit(message)

    def add_descriptions(self, target_item, descriptions, log):
        for description in descriptions:
            target_item.get()
            desc_content = descriptions[description]['value']
            lang = descriptions[description]['language']
            self.wdstuff.add_description(
                lang, desc_content, target_item)
            if log:
                t_id = target_item.getID()
                message = "{} ADDED DESCRIPTION {} {}".format(
                    t_id, lang, desc_content)
                log.logit(message)

    def make_descriptions(self):
        descriptions = self.data["descriptions"]
        new_descriptions = {}
        for item in descriptions:
            new_descriptions[item] = {
                'language': item, 'value': descriptions[item]}
        return new_descriptions

    def make_image_item(self, filename):
        commonssite = utils.create_site_instance("commons", "commons")
        imagelink = pywikibot.Link(
            filename, source=commonssite, defaultNamespace=6)
        return pywikibot.FilePage(imagelink)

    def make_coords_item(self, coordstuple):
        """
        Create a Coordinate item.

        Default precision, such as used by
        http://pywikibot.readthedocs.io/en/latest/_modules/scripts/claimit/
        """
        DEFAULT_PREC = 0.0001
        return pywikibot.Coordinate(
            coordstuple[0], coordstuple[1], precision=DEFAULT_PREC)

    def make_quantity_item(self, quantity, repo):
        """
        Create claim for a quantity, with optional unit.

        quantity: {'unit': 'Q11573', 'quantity_value': 6.85}
        """
        value = quantity['quantity_value']
        if 'unit' in quantity:
            unit = self.make_q_item(quantity['unit'])
        else:
            unit = None
        return pywikibot.WbQuantity(amount=value, unit=unit, site=repo)

    def make_time_item(self, quantity, repo):
        """
        Create a WbTime item.

        This only works for full years.
        TODO
        Make it work for year range!
        """
        value = quantity['time_value']
        return pywikibot.WbTime(**value)

    def make_q_item(self, qnumber):
        """Create a regular Item."""
        return self.wdstuff.QtoItemPage(qnumber)

    def item_has_prop(self, property_name, wd_item):
        """
        Check if item has a specific property.

        This is different from WikidataStuff has_claim()
        because it checks whether the property exists,
        not if the statement matches.
        If the target item already uses the property,
        a new claim will not be added even if it's different.
        """
        if PROPS[property_name] in wd_item.claims:
            return True
        else:
            return False

    def make_pywikibot_item(self, value, prop=None):
        val_item = None
        if type(value) is list and len(value) == 1:
            value = value[0]
        if utils.string_is_q_item(value):
            val_item = self.make_q_item(value)
        elif prop == PROPS["image"]:
            if not self.item_has_prop("image", self.wd_item) and \
                    utils.file_is_on_commons(value):
                val_item = self.make_image_item(value)
        elif utils.tuple_is_coords(value) and prop == PROPS["coordinates"]:
            # Don't upload coords if item already has one.
            # Temp. until https://phabricator.wikimedia.org/T160282 is solved.
            if not self.item_has_prop("coordinates", self.wd_item):
                val_item = self.make_coords_item(value)
        elif isinstance(value, dict) and 'quantity_value' in value:
            val_item = self.make_quantity_item(value, self.repo)
        elif isinstance(value, dict) and 'time_value' in value:
            val_item = self.make_time_item(value, self.repo)
        elif prop == PROPS["commonscat"] and utils.commonscat_exists(value):
            val_item = value
        else:
            val_item = value
        return val_item

    def make_statement(self, value):
        return self.wdstuff.Statement(value)

    def make_url_reference(self, uri):
        prop = PROPS["reference_url"]
        ref = self.wdstuff.Reference(
            source_test=self.wdstuff.make_simple_claim(prop, uri))
        return ref

    def make_stated_in_reference(self, ref_dict):
        prop = ref_dict["source"]["prop"]
        prop_date = ref_dict["published"]["prop"]
        date = ref_dict["published"]["value"]
        date_item = pywikibot.WbTime(**date)
        source_item = self.wdstuff.QtoItemPage(ref_dict["source"]["value"])
        source_claim = self.wdstuff.make_simple_claim(prop, source_item)
        if "reference_url" in ref_dict:
            ref_url = ref_dict["reference_url"]["value"]
            ref_url_prop = ref_dict["reference_url"]["prop"]
            ref_url_claim = self.wdstuff.make_simple_claim(
                ref_url_prop, ref_url)
            ref = self.wdstuff.Reference(
                source_test=[source_claim, ref_url_claim],
                source_notest=self.wdstuff.make_simple_claim(prop_date, date_item))
        else:
            ref = self.wdstuff.Reference(
                source_test=[source_claim],
                source_notest=self.wdstuff.make_simple_claim(prop_date, date_item))
        return ref

    def add_claims(self, wd_item, claims, log):
        if wd_item:
            for claim in claims:
                prop = claim
                for x in claims[claim]:
                    value = x['value']
                    if value != "":
                        ref = None
                        quals = x['quals']
                        refs = x['refs']
                        wd_claim = self.make_pywikibot_item(value, prop)
                        if wd_claim is None:
                            continue
                        wd_value = self.make_statement(wd_claim)
                        if any(quals):
                            for qual in quals:
                                value = self.make_pywikibot_item(
                                    quals[qual], qual)
                                qualifier = self.wdstuff.Qualifier(qual, value)
                                wd_value.addQualifier(qualifier)
                        for ref in refs:
                            # This only works if it's a url.
                            # If we have references of different sort,
                            # this will have to be appended.
                            if utils.is_valid_url(ref):
                                ref = self.make_url_reference(ref)
                            else:
                                ref = self.make_stated_in_reference(ref)
                        if wd_value:
                            self.wdstuff.addNewClaim(
                                prop, wd_value, wd_item, ref)
                            if log:
                                t_id = wd_item.getID()
                                message = "{} ADDED CLAIM {}".format(
                                    t_id, prop)
                                log.logit(message)

    def create_new_item(self, log):
        item = self.wdstuff.make_new_item({}, self.summary)
        if log:
            t_id = item.getID()
            message = "{} CREATE".format(t_id)
            log.logit(message)
        return item

    def get_username(self):
        """Get Wikidata login that will be used to upload."""
        return pywikibot.config.usernames["wikidata"]["wikidata"]

    def upload(self):
        if self.data["upload"] is False:
            print("SKIPPING ITEM")
            return
        labels = self.make_labels()
        descriptions = self.make_descriptions()
        aliases = self.make_aliases()
        claims = self.data["statements"]
        self.add_labels(self.wd_item, labels, aliases, self.log)
        self.add_descriptions(self.wd_item, descriptions, self.log)
        self.add_claims(self.wd_item, claims, self.log)

    def set_wd_item(self):
        """
        Determine WD item to manipulate.

        In live mode, if data object has associated WD item,
        edit it. Otherwise, create a new WD item.
        In sandbox mode, all edits are done on the WD Sandbox item.
        """
        if self.live:
            if self.data["wd-item"] is None:
                self.wd_item = self.create_new_item(self.log)
                self.wd_item_q = self.wd_item.getID()
            else:
                item_q = self.data["wd-item"]
                self.wd_item = self.wdstuff.QtoItemPage(item_q)
                self.wd_item_q = item_q
        else:
            self.wd_item = self.wdstuff.QtoItemPage(self.TEST_ITEM)
            self.wd_item_q = self.TEST_ITEM

    def __init__(self,
                 monument_object,
                 repo,
                 log=None,
                 tablename=None,
                 live=False):
        """
        Initialize an Upload object for a single Monument.

        :param monument_object: Dictionary of Monument data
        :param repo: Data repository of site to work on (Wikidata)
        :param log: Enable logging to file
        :param tablename: Name of db table, used in edit summary
        :param live: Whether to work on real WD items or in the sandbox
        """
        self.repo = repo
        self.log = False
        self.summary = "test"
        self.live = live
        print("User: {}".format(self.get_username()))
        print("Edit summary: {}".format(self.summary))
        if self.live:
            print("LIVE MODE")
        else:
            print("SANDBOX MODE: {}".format(self.TEST_ITEM))
        print("---------------")
        if log is not None:
            self.log = log
        self.data = monument_object.wd_item
        self.wdstuff = WDS(self.repo, edit_summary=self.summary)
        self.set_wd_item()