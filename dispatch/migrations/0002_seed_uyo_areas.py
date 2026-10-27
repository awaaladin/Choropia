from django.db import migrations
from django.utils.text import slugify

# A starting list of well-known Uyo areas. Drivers and users can add more; staff can hide any.
UYO_AREAS = [
    "Ewet Housing", "Shelter Afrique", "Osongama Estate", "Use Offot", "Aka Offot", "Anua", "Itam",
    "Ikot Ekpene Road", "Abak Road", "Oron Road", "Nwaniba Road", "Udo Udoma Avenue", "Four Lanes",
    "Wellington Bassey Way", "Ibom Plaza", "Itu Road", "Mbiabong", "Ikot Oku Ikono", "Afaha Oku",
    "Ikot Akpan Abia", "Ibesikpo", "Uniuyo Town Campus", "Uniuyo Permanent Site", "Uyo Village Road",
    "Aka Road", "Idoro Road", "Atiku Abubakar Avenue", "Ikot Ntuen", "Uyo Main Market", "Akpan Andem Market",
]


def seed(apps, schema_editor):
    Area = apps.get_model("dispatch", "Area")
    for name in UYO_AREAS:
        Area.objects.get_or_create(slug=slugify(name), defaults={"name": name, "is_seed": True})


def unseed(apps, schema_editor):
    apps.get_model("dispatch", "Area").objects.filter(is_seed=True, added_by__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("dispatch", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
