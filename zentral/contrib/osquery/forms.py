from datetime import datetime, timedelta
from django import forms
from django.db.models import Count, F, Q
from django.utils.text import slugify
from .compliance_checks import sync_query_compliance_check
from .models import (AutomaticTableConstruction, Configuration, ConfigurationPack,
                     DistributedQuery, Enrollment, FileCategory, Pack, PackQuery, Platform, Query)
from .releases import get_osquery_versions


# common

class PlatformsWidget(forms.CheckboxSelectMultiple):
    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs, choices=Platform.choices())

    def format_value(self, value):
        if isinstance(value, str) and value:
            value = [v.strip() for v in value.split(",")]
        return super().format_value(value)


# ATC

class ATCForm(forms.ModelForm):
    class Meta:
        model = AutomaticTableConstruction
        fields = "__all__"
        widgets = {"platforms": PlatformsWidget}


# Configuration

class ConfigurationForm(forms.ModelForm):
    class Meta:
        model = Configuration
        fields = "__all__"

    def clean_options(self):
        options = self.cleaned_data.get("options")
        if not options:
            options = {}
        return options


# Configuration pack

class ConfigurationPackForm(forms.ModelForm):
    class Meta:
        model = ConfigurationPack
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.configuration = kwargs.pop("configuration", None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["pack"].widget = forms.HiddenInput()
            self.configuration = self.instance.configuration
            self.fields["pack"].queryset = Pack.objects.filter(pk=self.instance.pack.pk)
        else:
            self.fields["pack"].queryset = (Pack.objects.exclude(configurationpack__configuration=self.configuration)
                                                        .order_by("name", "pk"))

    def clean(self):
        super().clean()
        self.instance.configuration = self.configuration


# Distributed query

class DistributedQueryForm(forms.ModelForm):
    halt_current_runs = forms.BooleanField(initial=True, required=False)

    class Meta:
        model = DistributedQuery
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.query = kwargs.pop("query", None)
        super().__init__(*args, **kwargs)
        self.fields["valid_from"].initial = datetime.utcnow()
        if not self.instance.pk:
            self.fields["valid_until"].initial = datetime.utcnow() + timedelta(hours=1)
            current_runs = self.query.distributedquery_set.active().count()
            if current_runs:
                self.fields["halt_current_runs"].label = "Halt current run{}".format("" if current_runs == 1 else "s")
            else:
                self.fields["halt_current_runs"].widget = forms.HiddenInput()
        else:
            self.fields["halt_current_runs"].widget = forms.HiddenInput()

    def clean(self):
        # valid until
        valid_until = self.cleaned_data.get("valid_until")
        if valid_until:
            valid_from = self.cleaned_data.get("valid_from")
            if valid_from and valid_until < valid_from:
                self.add_error("valid_until", "Valid until must be greater than valid from")
            if not self.instance.pk and valid_until < datetime.utcnow():
                self.add_error("valid_until", "Valid until is in the past")

        # default values
        if self.query:
            self.instance.query = self.query
            self.instance.sql = self.query.sql
            self.instance.query_version = self.query.version
            self.instance.platforms = self.query.platforms
            self.instance.minimum_osquery_version = self.query.minimum_osquery_version

    def save(self, *args, **kwargs):
        if not self.instance.pk and self.cleaned_data.get("halt_current_runs"):
            self.query.distributedquery_set.active().update(valid_until=datetime.utcnow())
        return super().save(*args, **kwargs)


# Enrollment

class EnrollmentForm(forms.ModelForm):
    osquery_release = forms.ChoiceField(
        label="Osquery release",
        choices=[],
        initial="",
        help_text="Choose an osquery release to be installed by the enrollment package.",
        required=False
    )

    class Meta:
        model = Enrollment
        fields = ("configuration", "osquery_release")

    def __init__(self, *args, **kwargs):
        # meta business unit not used in this enrollment form
        self.meta_business_unit = kwargs.pop("meta_business_unit", None)
        self.configuration = kwargs.pop("configuration", None)
        self.enrollment_only = kwargs.pop("enrollment_only", False)
        self.standalone = kwargs.pop("standalone", False)
        super().__init__(*args, **kwargs)
        # hide configuration dropdown if configuration if fixed
        if self.configuration:
            self.fields["configuration"].widget = forms.HiddenInput()

        # release
        release_field = self.fields["osquery_release"]
        if self.enrollment_only:
            release_field.widget = forms.HiddenInput()
        else:
            release_choices = [
                (version,
                 "{}{} ({})".format(
                     version,
                     " - prerelease -" if prerelease else "",
                     ", ".join(sorted(available_assets.keys()))
                 ))
                for version, prerelease, available_assets in get_osquery_versions()
            ]
            if not self.standalone:
                release_choices.insert(0, ("", "Do not include osquery"))
            release_field.choices = release_choices


# File category

class FileCategoryForm(forms.ModelForm):
    class Meta:
        model = FileCategory
        fields = "__all__"

    def clean(self):
        super().clean()
        name = self.cleaned_data.get("name")
        if name:
            slug = slugify(name)
            fc_qs = FileCategory.objects.all()
            if self.instance.pk:
                fc_qs = fc_qs.exclude(pk=self.instance.pk)
            if fc_qs.filter(slug=slug).exists():
                self.add_error("name", f"A file category with the slug '{slug}' already exists")
            else:
                self.instance.slug = slug


# Pack

class PackForm(forms.ModelForm):
    class Meta:
        model = Pack
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        name = self.cleaned_data.get("name")
        if name:
            slug = slugify(name)
            pack_qs = Pack.objects.all()
            if self.instance.pk:
                pack_qs = pack_qs.exclude(pk=self.instance.pk)
            if pack_qs.filter(slug=slug).exists():
                self.add_error("name", f"A pack with the slug '{slug}' already exists")
            else:
                self.instance.slug = slug


# Pack query

class PackQueryForm(forms.ModelForm):
    class Meta:
        model = PackQuery
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        self.pack = kwargs.pop("pack", None)
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["query"].widget = forms.HiddenInput()
            self.pack = self.instance.pack
            self.fields["query"].queryset = Query.objects.filter(pk=self.instance.query.pk)
            if self.instance.query and self.instance.query.compliance_check:
                # force snapshot mode
                self.fields["log_removed_actions"].disabled = True
                self.fields["snapshot_mode"].disabled = True
        else:
            self.fields["query"].queryset = (Query.objects.filter(packquery__isnull=True)
                                                          .order_by("name", "pk"))

    def clean(self):
        super().clean()
        if self.cleaned_data.get("log_removed_actions") and self.cleaned_data.get("snapshot_mode"):
            for field in ("log_removed_actions", "snapshot_mode"):
                self.add_error(field, "'Log removed actions' and 'Snapshot mode' are mutually exclusive")
        self.instance.pack = self.pack
        query = self.cleaned_data.get("query")
        if query:
            self.instance.slug = slugify(query.name)
            if query.compliance_check and not self.cleaned_data.get("snapshot_mode"):
                self.add_error("snapshot_mode", "A compliance check query can only be scheduled in 'snapshot' mode.")


# Query

class QueryForm(forms.ModelForm):
    compliance_check = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["compliance_check"].initial = self.instance.compliance_check is not None

    class Meta:
        model = Query
        fields = "__all__"
        widgets = {"platforms": PlatformsWidget,
                   "description": forms.Textarea(attrs={"rows": 2}),
                   "value": forms.Textarea(attrs={"rows": 2})}

    def clean_sql(self):
        sql = self.cleaned_data.get("sql")
        if self.instance.pk:
            if sql and sql != self.instance.sql:
                self.instance.version = F("version") + 1
        return sql

    def clean(self):
        if self.cleaned_data.get("compliance_check"):
            sql = self.cleaned_data.get("sql")
            if sql and "ztl_status" not in sql:
                self.add_error(
                    "compliance_check",
                    "The query doesn't contain the 'ztl_status' keyword"
                )
            try:
                pack_query = self.instance.packquery
            except PackQuery.DoesNotExist:
                pass
            else:
                if not pack_query.snapshot_mode:
                    self.add_error(
                        "compliance_check",
                        f"This query is scheduled in 'diff' mode in the {pack_query.pack} pack"
                    )

    def save(self, *args, **kwargs):
        query = super().save(*args, **kwargs)
        sync_query_compliance_check(query, self.cleaned_data.get("compliance_check"))
        return query


class QuerySearchForm(forms.Form):
    q = forms.CharField(
        label="Query", required=False,
        widget=forms.TextInput(attrs={"autofocus": True,
                                      "size": 36,
                                      "placeholder": "Query name, pack name, SQL, …"})
    )
    pack = forms.ModelChoiceField(queryset=Pack.objects.all(), required=False)
    compliance_check = forms.BooleanField(label="Only compliance checks", required=False)

    def get_queryset(self):
        qs = (
            Query.objects
                 .select_related("compliance_check")
                 .prefetch_related("packquery__pack")
                 .annotate(distributed_query_count=Count("distributedquery"))
                 .order_by("name", "pk")
        )
        q = self.cleaned_data.get("q")
        pack = self.cleaned_data.get("pack")
        if q or pack:
            qs = qs.distinct()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(sql__icontains=q)
                | Q(packquery__pack__name__icontains=q)
            )
        if pack:
            qs = qs.filter(packquery__pack=pack)
        if self.cleaned_data.get("compliance_check"):
            qs = qs.filter(compliance_check__isnull=False)
        return qs
