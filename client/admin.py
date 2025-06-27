from django.contrib import admin
from .models import Event,Activity
from django.contrib.admin import ModelAdmin
# Register your models here.
admin.site.register(Event)
class ActivityAdmin(ModelAdmin):
    list_display=['user','activity_type','timestamp']
admin.site.register(Activity,ActivityAdmin)