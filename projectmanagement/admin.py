from django.contrib import admin
from .models import *
# Register your models here.

admin.site.register(TaskDependency)
admin.site.register(KanbanBoard)
admin.site.register(KanbanColumn)
admin.site.register(KanbanTask)
admin.site.register(TemplateTask)
admin.site.register(TemplateDependency)


