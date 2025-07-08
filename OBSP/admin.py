from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django import forms
from .models import OBSPAssignmentNote,OBSPAssignment,OBSPTemplate, OBSPLevel, OBSPField, OBSPResponse,OBSPCriteria, OBSPMilestone, OBSPApplication
import re
from django.utils import timezone
from django.contrib.auth import get_user_model
import json

User = get_user_model()

admin.site.register(OBSPCriteria)
admin.site.register(OBSPAssignmentNote)

class OBSPLevelForm(forms.ModelForm):
    """Custom form for OBSP levels with better feature/deliverable handling"""
    features_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'Enter features one per line:\n5-page responsive website\nBasic product catalog\nSimple checkout process\nAdmin dashboard (basic)\nMobile responsive design\nBasic SEO setup'
        }),
        required=False,
        help_text="Enter features one per line. Each line will become a separate feature."
    )
    
    deliverables_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': 'Enter deliverables one per line:\nFully functional website\nAdmin panel access\nBasic documentation\n1 month support'
        }),
        required=False,
        help_text="Enter deliverables one per line. Each line will become a separate deliverable."
    )
    
    class Meta:
        model = OBSPLevel
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'size': 40}),
            'price': forms.NumberInput(attrs={'min': 0, 'step': 100, 'style': 'width: 150px;'}),
            'duration': forms.TextInput(attrs={'size': 30}),
            'order': forms.NumberInput(attrs={'min': 1, 'style': 'width: 80px;'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Convert features back to text
            if self.instance.features:
                self.fields['features_text'].initial = '\n'.join(self.instance.features)
            
            # Convert deliverables back to text
            if self.instance.deliverables:
                self.fields['deliverables_text'].initial = '\n'.join(self.instance.deliverables)
    
    def clean_features_text(self):
        """Convert features text to list"""
        features_text = self.cleaned_data.get('features_text', '')
        if features_text:
            features = [line.strip() for line in features_text.split('\n') if line.strip()]
            return features
        return []
    
    def clean_deliverables_text(self):
        """Convert deliverables text to list"""
        deliverables_text = self.cleaned_data.get('deliverables_text', '')
        if deliverables_text:
            deliverables = [line.strip() for line in deliverables_text.split('\n') if line.strip()]
            return deliverables
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set features and deliverables from text
        instance.features = self.cleaned_data.get('features_text', [])
        instance.deliverables = self.cleaned_data.get('deliverables_text', [])
        
        if commit:
            instance.save()
        return instance

class OBSPLevelInline(admin.TabularInline):
    model = OBSPLevel
    form = OBSPLevelForm
    extra = 0
    fields = ('level', 'name', 'price', 'duration', 'is_active', 'order', 'features_text', 'deliverables_text')
    ordering = ('order',)
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Customize field widgets for better layout
        formset.form.base_fields['level'].widget.attrs.update({'style': 'width: 100px;'})
        formset.form.base_fields['name'].widget.attrs.update({'style': 'width: 200px;'})
        formset.form.base_fields['price'].widget.attrs.update({'style': 'width: 120px;'})
        formset.form.base_fields['duration'].widget.attrs.update({'style': 'width: 120px;'})
        formset.form.base_fields['order'].widget.attrs.update({'style': 'width: 60px;'})
        formset.form.base_fields['features_text'].widget.attrs.update({'style': 'width: 300px; height: 100px;'})
        formset.form.base_fields['deliverables_text'].widget.attrs.update({'style': 'width: 300px; height: 100px;'})
        return formset

class OBSPFieldForm(forms.ModelForm):
    """Custom form for OBSP fields with better option handling and pricing"""
    options_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 8, 
            'placeholder': 'Enter options one per line:\n\nFormat: Option Name ~[Price] | Description\n\nExamples:\nBasic Package ~[5000] | 5 pages, contact form\nStandard Package ~[15000] | 10 pages, e-commerce integration\nPremium Package ~[25000] | Unlimited pages, custom design\n\nFor options without price:\nFree consultation\nBasic support'
        }),
        required=False,
        help_text="<strong>Option Format:</strong><br>• <code>Option Name ~[Price] | Description</code><br><br><strong>Examples:</strong><br>• <code>Basic Package ~[5000] | 5 pages, contact form</code><br>• <code>Standard Package ~[15000] | 10 pages, e-commerce integration</code><br>• <code>Premium Package ~[25000] | Unlimited pages, custom design</code><br>• <code>Free consultation</code> (no price)<br><br><strong>Rules:</strong><br>• Price: Use <code>~[amount]</code> format<br>• Description: Use <code>|</code> separator<br>• One option per line<br>• No price = no <code>~[amount]</code> needed"
    )
    
    class Meta:
        model = OBSPField
        fields = '__all__'
        widgets = {
            'label': forms.TextInput(attrs={'size': 40}),
            'placeholder': forms.TextInput(attrs={'size': 40}),
            'help_text': forms.TextInput(attrs={'size': 50}),
            'order': forms.NumberInput(attrs={'min': 1, 'style': 'width: 80px;'}),
            'price_impact': forms.NumberInput(attrs={'min': 0, 'step': 100, 'style': 'width: 120px;'}),
            'phase': forms.Select(attrs={'style': 'width: 200px;'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.options:
            # Convert options back to text format with pricing and description
            options_text = []
            for option in self.instance.options:
                if isinstance(option, dict):
                    text = option.get('text', '')
                    price = option.get('price', 0)
                    description = option.get('description', '')
                    
                    if price > 0 and description:
                        options_text.append(f"{text} ~[{price:.0f}] | {description}")
                    elif price > 0:
                        options_text.append(f"{text} ~[{price:.0f}]")
                    elif description:
                        options_text.append(f"{text} | {description}")
                    else:
                        options_text.append(text)
                else:
                    options_text.append(option)
            self.fields['options_text'].initial = '\n'.join(options_text)
    
    def clean_options_text(self):
        """Validate and parse options text with price and description"""
        options_text = self.cleaned_data.get('options_text', '')
        
        # Handle both string and list inputs
        if isinstance(options_text, list):
            return options_text
        elif isinstance(options_text, str):
            if not options_text.strip():
                return []
            
            options = []
            for line in options_text.split('\n'):
                line = line.strip()
                if line:
                    # Parse the line: "Option Name ~[Price] | Description"
                    option_data = {
                        'text': line,
                        'price': 0,
                        'description': ''
                    }
                    
                    # Check for price format ~[amount]
                    price_match = re.search(r'~\[(\d+(?:\.\d+)?)\]', line)
                    if price_match:
                        option_data['price'] = float(price_match.group(1))
                        # Remove price from text
                        line = re.sub(r'~\[\d+(?:\.\d+)?\]', '', line).strip()
                    
                    # Check for description format | description
                    if '|' in line:
                        parts = line.split('|', 1)
                        option_data['text'] = parts[0].strip()
                        option_data['description'] = parts[1].strip()
                    else:
                        option_data['text'] = line.strip()
                    
                    options.append(option_data)
            return options
        else:
            return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        options_text = self.cleaned_data.get('options_text', '')
        
        # Parse options if it's a string
        if isinstance(options_text, str):
            instance.options = self.clean_options_text()
        elif isinstance(options_text, list):
            instance.options = options_text
        else:
            instance.options = []
        
        # Update has_price_impact based on options
        if instance.options:
            has_pricing = any(opt.get('price', 0) > 0 for opt in instance.options)
            instance.has_price_impact = has_pricing
        
        if commit:
            instance.save()
        return instance

class OBSPFieldInline(admin.TabularInline):
    model = OBSPField
    form = OBSPFieldForm
    extra = 1
    fields = ('field_type', 'label', 'placeholder', 'help_text', 'visibility_rule', 'phase', 'is_required', 'has_price_impact', 'price_impact', 'order', 'options_text')
    ordering = ('phase', 'order')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Customize field widgets for better layout
        formset.form.base_fields['field_type'].widget.attrs.update({'style': 'width: 120px;'})
        formset.form.base_fields['label'].widget.attrs.update({'style': 'width: 200px;'})
        formset.form.base_fields['placeholder'].widget.attrs.update({'style': 'width: 180px;'})
        formset.form.base_fields['help_text'].widget.attrs.update({'style': 'width: 250px;'})
        formset.form.base_fields['visibility_rule'].widget.attrs.update({'style': 'width: 120px;'})
        formset.form.base_fields['phase'].widget.attrs.update({'style': 'width: 150px;'})
        formset.form.base_fields['order'].widget.attrs.update({'style': 'width: 60px;'})
        formset.form.base_fields['price_impact'].widget.attrs.update({'style': 'width: 100px;'})
        formset.form.base_fields['options_text'].widget.attrs.update({'style': 'width: 350px; height: 100px;'})
        return formset

class OBSPMilestoneForm(forms.ModelForm):
    """Custom form for OBSP milestones with better deliverable/checklist handling"""
    deliverables_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Enter deliverables one per line:\nWireframes and mockups\nDesign system documentation\nResponsive design files\nDesign handoff package'
        }),
        required=False,
        help_text="Enter deliverables one per line. Each line will become a separate deliverable."
    )
    
    quality_checklist_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Enter quality checklist items one per line:\nAll pages designed according to brand guidelines\nMobile responsive design implemented\nDesign files properly organized\nClient feedback incorporated'
        }),
        required=False,
        help_text="Enter quality checklist items one per line. Each line will become a separate checklist item."
    )
    
    class Meta:
        model = OBSPMilestone
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'size': 40}),
            'description': forms.Textarea(attrs={'rows': 3, 'cols': 50}),
            'estimated_days': forms.NumberInput(attrs={'min': 1, 'style': 'width: 100px;'}),
            'payout_percentage': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': 5, 'style': 'width: 100px;'}),
            'order': forms.NumberInput(attrs={'min': 1, 'style': 'width: 80px;'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Convert deliverables back to text
            if self.instance.deliverables:
                self.fields['deliverables_text'].initial = '\n'.join(self.instance.deliverables)
            
            # Convert quality checklist back to text
            if self.instance.quality_checklist:
                self.fields['quality_checklist_text'].initial = '\n'.join(self.instance.quality_checklist)
    
    def clean_deliverables_text(self):
        """Convert deliverables text to list"""
        deliverables_text = self.cleaned_data.get('deliverables_text', '')
        if deliverables_text:
            deliverables = [line.strip() for line in deliverables_text.split('\n') if line.strip()]
            return deliverables
        return []
    
    def clean_quality_checklist_text(self):
        """Convert quality checklist text to list"""
        checklist_text = self.cleaned_data.get('quality_checklist_text', '')
        if checklist_text:
            checklist = [line.strip() for line in checklist_text.split('\n') if line.strip()]
            return checklist
        return []
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set deliverables and quality checklist from text
        instance.deliverables = self.cleaned_data.get('deliverables_text', [])
        instance.quality_checklist = self.cleaned_data.get('quality_checklist_text', [])
        
        if commit:
            instance.save()
        return instance

class OBSPMilestoneInline(admin.TabularInline):
    model = OBSPMilestone
    form = OBSPMilestoneForm
    extra = 1
    fields = ('level', 'milestone_type', 'title', 'description', 'estimated_days', 'payout_percentage', 'order', 'client_approval_required', 'status', 'deliverables_text', 'quality_checklist_text')
    ordering = ('level', 'order')
    
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Customize field widgets for better layout
        formset.form.base_fields['level'].widget.attrs.update({'style': 'width: 120px;'})
        formset.form.base_fields['milestone_type'].widget.attrs.update({'style': 'width: 150px;'})
        formset.form.base_fields['title'].widget.attrs.update({'style': 'width: 200px;'})
        formset.form.base_fields['description'].widget.attrs.update({'style': 'width: 250px; height: 60px;'})
        formset.form.base_fields['estimated_days'].widget.attrs.update({'style': 'width: 100px;'})
        formset.form.base_fields['payout_percentage'].widget.attrs.update({'style': 'width: 100px;'})
        formset.form.base_fields['order'].widget.attrs.update({'style': 'width: 60px;'})
        formset.form.base_fields['deliverables_text'].widget.attrs.update({'style': 'width: 300px; height: 80px;'})
        formset.form.base_fields['quality_checklist_text'].widget.attrs.update({'style': 'width: 300px; height: 80px;'})
        return formset

@admin.register(OBSPTemplate)
class OBSPTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'industry', 'get_level_count', 'get_field_count', 'get_milestone_count', 'is_active', 'created_by', 'created_at')
    list_filter = ('category', 'industry', 'is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at', 'preview_link')
    inlines = [OBSPLevelInline, OBSPFieldInline, OBSPMilestoneInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'category', 'industry', 'description')
        }),
        ('Pricing', {
            'fields': ('base_price', 'currency')
        }),
        
        ('Status', {
            'fields': ('is_active', 'created_by')
        }),
        ('Preview', {
            'fields': ('preview_link',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def preview_link(self, obj):
        if obj.pk:
            return format_html(
                '<a href="{}" target="_blank" class="button">Preview OBSP Form</a>',
                reverse('obsp_preview', args=[obj.pk])
            )
        return "Save first to preview"
    preview_link.short_description = "Preview"
    
    def get_level_count(self, obj):
        return obj.levels.count()
    get_level_count.short_description = "Levels"
    
    def get_field_count(self, obj):
        return obj.fields.count()
    get_field_count.short_description = "Fields"
    
    def get_milestone_count(self, obj):
        return obj.template_milestones.count()
    get_milestone_count.short_description = "Milestones"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def duplicate_obsp(self, request, queryset):
        """Duplicate selected OBSP templates"""
        for obsp in queryset:
            # Create a copy of the OBSP
            new_obsp = OBSPTemplate.objects.create(
                title=f"{obsp.title} (Copy)",
                category=obsp.category,
                industry=obsp.industry,
                description=obsp.description,
                base_price=obsp.base_price,
                currency=obsp.currency,
                created_by=request.user
            )
            
            # Copy all levels
            for level in obsp.levels.all():
                new_level = OBSPLevel.objects.create(
                    template=new_obsp,
                    level=level.level,
                    name=level.name,
                    price=level.price,
                    duration=level.duration,
                    features=level.features,
                    deliverables=level.deliverables,
                    is_active=level.is_active,
                    order=level.order
                )
                
                # Copy milestones for this level
                for milestone in level.level_milestones.all():
                    OBSPMilestone.objects.create(
                        template=new_obsp,
                        level=new_level,
                        milestone_type=milestone.milestone_type,
                        title=milestone.title,
                        description=milestone.description,
                        estimated_days=milestone.estimated_days,
                        payout_percentage=milestone.payout_percentage,
                        deliverables=milestone.deliverables,
                        quality_checklist=milestone.quality_checklist,
                        client_approval_required=milestone.client_approval_required,
                        status=milestone.status,
                        order=milestone.order
                    )
            
            # Copy all fields
            for field in obsp.fields.all():
                OBSPField.objects.create(
                    template=new_obsp,
                    field_type=field.field_type,
                    label=field.label,
                    placeholder=field.placeholder,
                    help_text=field.help_text,
                    is_required=field.is_required,
                    has_price_impact=field.has_price_impact,
                    price_impact=field.price_impact,
                    order=field.order,
                    options=field.options,
                    visibility_rule=field.visibility_rule
                )
        
        self.message_user(request, f"Successfully duplicated {queryset.count()} OBSP(s)")
    duplicate_obsp.short_description = "Duplicate selected OBSPs"

    def activate_obsp(self, request, queryset):
        """Activate selected OBSP templates"""
        queryset.update(is_active=True)
        self.message_user(request, f"Successfully activated {queryset.count()} OBSP(s)")
    activate_obsp.short_description = "Activate selected OBSPs"

    def deactivate_obsp(self, request, queryset):
        """Deactivate selected OBSP templates"""
        queryset.update(is_active=False)
        self.message_user(request, f"Successfully deactivated {queryset.count()} OBSP(s)")
    deactivate_obsp.short_description = "Deactivate selected OBSPs"

    actions = [duplicate_obsp, activate_obsp, deactivate_obsp]

@admin.register(OBSPLevel)
class OBSPLevelAdmin(admin.ModelAdmin):
    form = OBSPLevelForm
    list_display = ('template', 'level', 'name', 'price', 'duration', 'is_active', 'order', 'get_features_count', 'get_deliverables_count')
    list_filter = ('level', 'is_active', 'template')
    search_fields = ('template__title', 'name')
    ordering = ('template', 'order')
    
    fieldsets = (
        ('Level Information', {
            'fields': ('template', 'level', 'name', 'order')
        }),
        ('Limits', {
            'fields': ('max_revisions',)
        }),
        ('Pricing & Timeline', {
            'fields': ('price', 'duration')
        }),
        ('Features', {
            'fields': ('features_text',),
            'description': 'Enter features one per line. Each line will become a separate feature.'
        }),
        ('Deliverables', {
            'fields': ('deliverables_text',),
            'description': 'Enter deliverables one per line. Each line will become a separate deliverable.'
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def get_features_count(self, obj):
        if obj.features:
            return f"{len(obj.features)} features"
        return "No features"
    get_features_count.short_description = "Features"
    
    def get_deliverables_count(self, obj):
        if obj.deliverables:
            return f"{len(obj.deliverables)} deliverables"
        return "No deliverables"
    get_deliverables_count.short_description = "Deliverables"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "template":
            kwargs["queryset"] = OBSPTemplate.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(OBSPField)
class OBSPFieldAdmin(admin.ModelAdmin):
    form = OBSPFieldForm
    list_display = ('label', 'template', 'field_type', 'visibility_rule', 'phase', 'is_required', 'has_price_impact', 'get_max_price', 'order', 'get_options_count')
    list_filter = ('field_type', 'visibility_rule', 'phase', 'is_required', 'has_price_impact', 'template')
    search_fields = ('label', 'template__title')
    ordering = ('template', 'phase', 'order')
    
    fieldsets = (
        ('Field Information', {
            'fields': ('template', 'field_type', 'label', 'placeholder', 'help_text')
        }),
        ('Visibility & Settings', {
            'fields': ('visibility_rule', 'phase', 'is_required', 'has_price_impact', 'price_impact', 'order')
        }),
        ('Options with Pricing', {
            'fields': ('options_text',),
            'description': '<strong>Option Pricing Format:</strong><br>• Basic option: "Option Name"<br>• Priced option: "Option Name ~[5000]"<br>• Examples:<br>&nbsp;&nbsp;Yes, I have all content<br>&nbsp;&nbsp;I need copywriting help ~[2000]<br>&nbsp;&nbsp;Complete content creation ~[5000]<br><br><strong>Pricing Logic:</strong><br>• Radio buttons: Only highest price is applied<br>• Checkboxes: Sum of all selected prices<br>• Select: Price of selected option'
        }),
    )
    
    def get_options_count(self, obj):
        if obj.options:
            return f"{len(obj.options)} options"
        return "No options"
    get_options_count.short_description = "Options"
    
    def get_max_price(self, obj):
        if obj.has_price_impact:
            return f"₹{obj.price_impact:,.0f}"
        elif obj.options:
            max_price = obj.get_total_price_impact()
            if max_price > 0:
                return f"₹{max_price:,.0f}"
        return "₹0"
    get_max_price.short_description = "Max Price"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "template":
            kwargs["queryset"] = OBSPTemplate.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

@admin.register(OBSPMilestone)
class OBSPMilestoneAdmin(admin.ModelAdmin):
    form = OBSPMilestoneForm
    list_display = ('id','template', 'level', 'milestone_type', 'title', 'estimated_days', 'payout_percentage', 'status', 'order', 'get_deliverables_count', 'get_checklist_count')
    list_filter = ('milestone_type', 'status', 'client_approval_required', 'template', 'level')
    search_fields = ('title', 'template__title', 'level__name')
    ordering = ('template', 'level', 'order')
    
    fieldsets = (
        ('Milestone Information', {
            'fields': ('template', 'level', 'milestone_type', 'title', 'description')
        }),
        ('Timeline & Payment', {
            'fields': ('estimated_days', 'payout_percentage', 'order')
        }),
        ('Deliverables', {
            'fields': ('deliverables_text',),
            'description': 'Enter deliverables one per line. Each line will become a separate deliverable.'
        }),
        ('Quality Assurance', {
            'fields': ('quality_checklist_text', 'client_approval_required')
        }),
        ('Status', {
            'fields': ('status',)
        }),
    )
    
    def get_deliverables_count(self, obj):
        if obj.deliverables:
            return f"{len(obj.deliverables)} deliverables"
        return "No deliverables"
    get_deliverables_count.short_description = "Deliverables"
    
    def get_checklist_count(self, obj):
        if obj.quality_checklist:
            return f"{len(obj.quality_checklist)} items"
        return "No checklist"
    get_checklist_count.short_description = "QA Checklist"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "template":
            kwargs["queryset"] = OBSPTemplate.objects.filter(is_active=True)
        elif db_field.name == "level":
            kwargs["queryset"] = OBSPLevel.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class OBSPResponseForm(forms.ModelForm):
    milestone_progress_text = forms.CharField(
        label="Milestone Progress (one per line: milestone_id - status)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'style': 'width: 100%;'}),
        help_text="Format: <code>milestone_id - status</code> (e.g. <code>21 - completed</code>)"
    )

    class Meta:
        model = OBSPResponse
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepopulate the text field from the JSON
        progress = self.instance.milestone_progress or {}
        lines = [f"{k} - {v}" for k, v in progress.items()]
        self.fields['milestone_progress_text'].initial = "\n".join(lines)

    def clean_milestone_progress_text(self):
        text = self.cleaned_data.get('milestone_progress_text', '')
        progress = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if '-' not in line:
                raise forms.ValidationError("Each line must be in the format: milestone_id - status")
            milestone_id, status = line.split('-', 1)
            progress[milestone_id.strip()] = status.strip()
        return progress

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.milestone_progress = self.cleaned_data.get('milestone_progress_text', {})
        if commit:
            instance.save()
        return instance

@admin.register(OBSPResponse)
class OBSPResponseAdmin(admin.ModelAdmin):
    form = OBSPResponseForm
    list_display = (
        'template', 'client', 'selected_level', 'total_price', 'status', 'created_at', 'current_milestone'
    )
    list_filter = ('status', 'selected_level', 'created_at', 'template')
    search_fields = ('template__title', 'client__username')
    readonly_fields = ('created_at', 'updated_at', 'responses_display')
    
    fieldsets = (
        ('Response Information', {
            'fields': ('template', 'client', 'selected_level', 'status', 'current_milestone')
        }),
        ('Pricing', {
            'fields': ('total_price',)
        }),
        ('Limits', {
            'fields': ('max_revisions',)
        }),
        ('Milestone Tracking', {
            'fields': ('milestone_progress_text',)
        }),
        ('Response Data', {
            'fields': ('responses_display',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def responses_display(self, obj):
        if obj.responses:
            html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">'
            for field_name, value in obj.responses.items():
                html += f'<div style="margin-bottom: 10px;"><strong>{field_name}:</strong> {value}</div>'
            html += '</div>'
            return mark_safe(html)
        return "No responses"
    responses_display.short_description = "Responses"

    def has_add_permission(self, request):
        # Responses should only be created through the frontend
        return False

# Custom admin site configuration
admin.site.site_header = "Talintz Admin"
admin.site.site_title = "Talintz Admin Portal"
admin.site.index_title = "Welcome to Talintz Administration"

class OBSPAssignmentForm(forms.ModelForm):
    """Custom form for OBSP assignments (milestone progress removed)"""

    class Meta:
        model = OBSPAssignment
        fields = '__all__'
        widgets = {
            'freelancer_payout': forms.NumberInput(attrs={'min': 0, 'step': 100, 'style': 'width: 150px;'}),
            'platform_fee': forms.NumberInput(attrs={'min': 0, 'step': 100, 'style': 'width: 150px;'}),
            'progress_percentage': forms.NumberInput(attrs={'min': 0, 'max': 100, 'style': 'width: 100px;'}),
            'quality_score': forms.NumberInput(attrs={'min': 0, 'max': 5, 'step': 0.1, 'style': 'width: 100px;'}),
        }

@admin.register(OBSPAssignment)
class OBSPAssignmentAdmin(admin.ModelAdmin):
    form = OBSPAssignmentForm
    list_display = (
        'get_project_info', 'assigned_freelancer', 'status', 'progress_percentage', 
        'get_financial_info', 'assigned_at', 'get_estimated_completion'
    )
    list_filter = (
        'status', 'assigned_at', 'deadline_met'
    )
    search_fields = (
        'obsp_response__template__title', 'assigned_freelancer__username',
        'obsp_response__client__username'
    )
    readonly_fields = (
        'assigned_at', 'started_at', 'completed_at', 'get_project_summary',
        'get_milestone_summary', 'get_financial_summary'
    )
    ordering = ('-assigned_at',)
    
    fieldsets = (
        ('Project Information', {
            'fields': (
                'obsp_response', 'assigned_freelancer', 'assigned_by', 'status'
            )
        }),
        ('Timeline & Progress', {
            'fields': (
                'progress_percentage',
                'assigned_at', 'started_at', 'completed_at'
            )
        }),
        ('Financial Details', {
            'fields': (
                'freelancer_payout', 'platform_fee', 'get_financial_summary'
            )
        }),
        ('Quality & Feedback', {
            'fields': (
                'quality_score', 'deadline_met'
            )
        }),
        ('Project Summary', {
            'fields': ('get_project_summary', 'get_milestone_summary'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['assign_freelancers', 'start_work', 'mark_completed', 'update_progress']
    
    def get_project_info(self, obj):
        """Display project information in list view"""
        template = obj.obsp_response.template.title
        client = obj.obsp_response.client.username
        level = obj.obsp_response.get_selected_level_display()
        
        return format_html(
            '<div><strong>{}</strong><br/>'
            '<small>Client: {} | Level: {}</small></div>',
            template, client, level
        )
    get_project_info.short_description = "Project"
    
    def get_financial_info(self, obj):
        """Display financial information in list view"""
        # Handle None values safely
        freelancer_payout = obj.freelancer_payout or 0
        platform_fee = obj.platform_fee or 0
        
        return format_html(
            '<div><strong>₹{}</strong><br/>'
            '<small>Platform: ₹{}</small></div>',
            f"{freelancer_payout:,.0f}", f"{platform_fee:,.0f}"
        )
    get_financial_info.short_description = "Payout"
    
    def get_estimated_completion(self, obj):
        """Display estimated completion date"""
        # Remove reference to obj.current_milestone
        # If you want to use milestone info, get it from obj.obsp_response.current_milestone
        current_milestone = getattr(obj.obsp_response, 'current_milestone', None)
        if current_milestone and obj.progress_percentage < 100:
            # If you have a method to get estimated completion date, update it to use obsp_response.current_milestone
            completion_date = obj.get_estimated_completion_date()  # You may need to update this method too!
            if completion_date:
                return completion_date.strftime('%b %d, %Y')
        return "N/A"
    get_estimated_completion.short_description = "Est. Completion"
    
    def get_project_summary(self, obj):
        """Display project summary"""
        response = obj.obsp_response
        template = response.template
        level_display = response.get_selected_level_display()
        
        # Handle None values safely
        total_price = response.total_price or 0
        
        html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h4>Project Summary</h4>
            <p><strong>Template:</strong> {template.title}</p>
            <p><strong>Category:</strong> {template.category.name}</p>
            <p><strong>Industry:</strong> {template.get_industry_display()}</p>
            <p><strong>Selected Level:</strong> {level_display}</p>
            <p><strong>Total Project Value:</strong> ₹{total_price:,.0f}</p>
            <p><strong>Client:</strong> {response.client.username}</p>
        </div>
        """
        return mark_safe(html)
    get_project_summary.short_description = "Project Summary"
    
    def get_milestone_summary(self, obj):
        """Display milestone summary"""
        if not obj.milestone_progress:
            return "No milestone progress recorded"
        
        html = '<div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">'
        html += '<h4>Milestone Progress</h4>'
        
        for milestone_name, data in obj.milestone_progress.items():
            if isinstance(data, dict):
                percentage = data.get('percentage', 0)
                notes = data.get('notes', '')
                updated_at = data.get('updated_at', '')
                
                # Color coding based on percentage
                if percentage == 100:
                    color = '#28a745'  # Green
                elif percentage >= 75:
                    color = '#17a2b8'  # Blue
                elif percentage >= 50:
                    color = '#ffc107'  # Yellow
                else:
                    color = '#dc3545'  # Red
                
                html += f"""
                <div style="margin-bottom: 10px; padding: 8px; border-left: 4px solid {color}; background: white;">
                    <strong>{milestone_name}</strong>: {percentage}%
                    {f'<br/><small>Notes: {notes}</small>' if notes else ''}
                    {f'<br/><small>Updated: {updated_at}</small>' if updated_at else ''}
                </div>
                """
        
        html += '</div>'
        return mark_safe(html)
    get_milestone_summary.short_description = "Milestone Summary"
    
    def get_financial_summary(self, obj):
        """Display financial summary"""
        # Handle None values safely
        freelancer_payout = obj.freelancer_payout or 0
        platform_fee = obj.platform_fee or 0
        total = freelancer_payout + platform_fee
        
        freelancer_percentage = (freelancer_payout / total * 100) if total > 0 else 0
        platform_percentage = (platform_fee / total * 100) if total > 0 else 0
        
        html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h4>Financial Breakdown</h4>
            <p><strong>Total Project Value:</strong> ₹{total:,.0f}</p>
            <p><strong>Freelancer Payout:</strong> ₹{freelancer_payout:,.0f} ({freelancer_percentage:.1f}%)</p>
            <p><strong>Platform Fee:</strong> ₹{platform_fee:,.0f} ({platform_percentage:.1f}%)</p>
        </div>
        """
        return mark_safe(html)
    get_financial_summary.short_description = "Financial Summary"
    
    # Admin Actions
    def assign_freelancers(self, request, queryset):
        """Assign freelancers to selected OBSP responses"""
        count = 0
        for assignment in queryset.filter(status='pending'):
            # Auto-assign logic can be implemented here
            assignment.status = 'assigned'
            assignment.assigned_by = request.user
            assignment.save()
            count += 1
        
        self.message_user(request, f"Successfully assigned {count} freelancer(s)")
    assign_freelancers.short_description = "Assign freelancers to selected projects"
    
    def start_work(self, request, queryset):
        """Start work on selected assignments"""
        count = 0
        for assignment in queryset.filter(status='assigned'):
            assignment.start_work()
            count += 1
        
        self.message_user(request, f"Started work on {count} assignment(s)")
    start_work.short_description = "Start work on selected assignments"
    
    def mark_completed(self, request, queryset):
        """Mark selected assignments as completed"""
        count = 0
        for assignment in queryset.filter(status__in=['in_progress', 'review']):
            assignment.complete_assignment()
            count += 1
        
        self.message_user(request, f"Marked {count} assignment(s) as completed")
    mark_completed.short_description = "Mark selected assignments as completed"
    
    def update_progress(self, request, queryset):
        """Update progress for selected assignments"""
        # This could open a custom form for bulk progress updates
        self.message_user(request, f"Progress update feature for {queryset.count()} assignment(s)")
    update_progress.short_description = "Update progress for selected assignments"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key fields"""
        if db_field.name == "assigned_freelancer":
            # Filter to show only users with freelancer role
            kwargs["queryset"] = User.objects.filter(role='freelancer', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'obsp_response__template',
            'obsp_response__client',
            'assigned_freelancer',
            'assigned_by'
        )

class OBSPApplicationForm(forms.ModelForm):
    """Custom form for OBSP applications with eligibility display"""
    
    class Meta:
        model = OBSPApplication
        fields = '__all__'
        widgets = {
            'pitch': forms.Textarea(attrs={'rows': 6, 'style': 'width: 100%;'}),
            'admin_notes': forms.Textarea(attrs={'rows': 4, 'style': 'width: 100%;'}),
            'rejection_reason': forms.Textarea(attrs={'rows': 3, 'style': 'width: 100%;'}),
        }

@admin.register(OBSPApplication)
class OBSPApplicationAdmin(admin.ModelAdmin):
    form = OBSPApplicationForm
    list_display = (
        'get_project_info', 'freelancer', 'selected_level', 'status', 
        'get_eligibility_score', 'applied_at', 'get_days_since'
    )
    list_filter = (
        'status', 'selected_level', 'applied_at', 'obsp_template__category'
    )
    search_fields = (
        'freelancer__username', 'obsp_template__title',
        'obsp_template__category__name'
    )
    readonly_fields = (
        'applied_at', 'get_eligibility_summary', 'get_project_summary',
        'get_freelancer_summary'
    )
    ordering = ('-applied_at',)
    
    fieldsets = (
        ('Application Information', {
            'fields': (
                'freelancer', 'obsp_template', 'selected_level', 'status'
            )
        }),
        ('Freelancer Pitch', {
            'fields': ('pitch',)
        }),
        ('Review Information', {
            'fields': (
                'reviewed_at', 'reviewed_by', 'admin_notes', 'rejection_reason'
            )
        }),
        ('Eligibility & Project Details', {
            'fields': (
                'eligibility_reference', 'get_eligibility_summary', 
                'get_project_summary', 'get_freelancer_summary'
            ),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_applications', 'reject_applications', 'assign_to_projects']
    
    def get_project_info(self, obj):
        """Display project information in list view"""
        template = obj.obsp_template.title
        category = obj.obsp_template.category.name
        level = obj.get_selected_level_display()
        
        return format_html(
            '<div><strong>{}</strong><br/>'
            '<small>Category: {} | Level: {}</small></div>',
            template, category, level
        )
    get_project_info.short_description = "Project"
    
    def get_eligibility_score(self, obj):
        """Display eligibility score with color coding"""
        score = obj.get_eligibility_score()
        if score >= 80:
            color = '#28a745'  # Green
        elif score >= 60:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color, score
        )
    get_eligibility_score.short_description = "Eligibility Score"
    
    def get_days_since(self, obj):
        """Display days since application"""
        days = obj.days_since_applied
        if days == 0:
            return "Today"
        elif days == 1:
            return "1 day ago"
        else:
            return f"{days} days ago"
    get_days_since.short_description = "Applied"
    
    def get_eligibility_summary(self, obj):
        """Display eligibility summary"""
        eligibility_data = obj.get_eligibility_data()
        if not eligibility_data:
            return "No eligibility data available"
        
        score = eligibility_data.get('score', 0)
        is_eligible = eligibility_data.get('is_eligible', False)
        proof = eligibility_data.get('proof', {})
        
        html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h4>Eligibility Analysis</h4>
            <p><strong>Score:</strong> <span style="color: {'green' if is_eligible else 'red'}; font-weight: bold;">{score}%</span></p>
            <p><strong>Status:</strong> <span style="color: {'green' if is_eligible else 'red'}; font-weight: bold;">{'Eligible' if is_eligible else 'Not Eligible'}</span></p>
        """
        
        if proof:
            html += '<h5>Analysis Details:</h5>'
            for key, value in proof.items():
                if key not in ['error'] and value:
                    html += f'<p><strong>{key.replace("_", " ").title()}:</strong> {value}</p>'
        
        html += '</div>'
        return mark_safe(html)
    get_eligibility_summary.short_description = "Eligibility Summary"
    
    def get_project_summary(self, obj):
        """Display project summary"""
        template = obj.obsp_template
        level_obj = template.levels.filter(level=obj.selected_level).first()
        
        html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h4>Project Summary</h4>
            <p><strong>Template:</strong> {template.title}</p>
            <p><strong>Category:</strong> {template.category.name}</p>
            <p><strong>Selected Level:</strong> {obj.get_selected_level_display()}</p>
            <p><strong>Project Value:</strong> ₹{obj.project_value:,.0f}</p>
            <p><strong>Industry:</strong> {template.get_industry_display()}</p>
        </div>
        """
        return mark_safe(html)
    get_project_summary.short_description = "Project Summary"
    
    def get_freelancer_summary(self, obj):
        """Display freelancer summary"""
        freelancer = obj.freelancer
        
        html = f"""
        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0;">
            <h4>Freelancer Summary</h4>
            <p><strong>Username:</strong> {freelancer.username}</p>
            <p><strong>Email:</strong> {freelancer.email}</p>
            <p><strong>Role:</strong> {freelancer.get_role_display()}</p>
            <p><strong>Member Since:</strong> {freelancer.date_joined.strftime('%B %d, %Y')}</p>
        </div>
        """
        return mark_safe(html)
    get_freelancer_summary.short_description = "Freelancer Summary"
    
    # Admin Actions
    def approve_applications(self, request, queryset):
        """Approve selected applications"""
        count = 0
        for application in queryset.filter(status='pending'):
            application.approve(request.user)
            count += 1
        
        self.message_user(request, f"Successfully approved {count} application(s)")
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        """Reject selected applications"""
        count = 0
        for application in queryset.filter(status='pending'):
            application.reject(request.user, "Bulk rejection")
            count += 1
        
        self.message_user(request, f"Successfully rejected {count} application(s)")
    reject_applications.short_description = "Reject selected applications"
    
    def assign_to_projects(self, request, queryset):
        """Assign approved applications to projects"""
        count = 0
        for application in queryset.filter(status='approved'):
            assignment = application.assign_to_project()
            if assignment:
                count += 1
        
        self.message_user(request, f"Successfully assigned {count} application(s) to projects")
    assign_to_projects.short_description = "Assign to projects"
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter foreign key fields"""
        if db_field.name == "freelancer":
            # Filter to show only users with freelancer role
            kwargs["queryset"] = User.objects.filter(role='freelancer', is_active=True)
        elif db_field.name == "reviewed_by":
            # Filter to show only staff users
            kwargs["queryset"] = User.objects.filter(is_staff=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'freelancer',
            'obsp_template__category',
            'reviewed_by',
            'eligibility_reference'
        )

class OBSPResponseForm(forms.ModelForm):
    milestone_progress_text = forms.CharField(
        label="Milestone Progress (one per line: milestone_id - status)",
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'style': 'width: 100%;'}),
        help_text="Format: <code>milestone_id - status</code> (e.g. <code>21 - completed</code>)"
    )

    class Meta:
        model = OBSPResponse
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepopulate the text field from the JSON
        progress = self.instance.milestone_progress or {}
        lines = [f"{k} - {v}" for k, v in progress.items()]
        self.fields['milestone_progress_text'].initial = "\n".join(lines)

    def clean_milestone_progress_text(self):
        text = self.cleaned_data.get('milestone_progress_text', '')
        progress = {}
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if '-' not in line:
                raise forms.ValidationError("Each line must be in the format: milestone_id - status")
            milestone_id, status = line.split('-', 1)
            progress[milestone_id.strip()] = status.strip()
        return progress

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.milestone_progress = self.cleaned_data.get('milestone_progress_text', {})
        if commit:
            instance.save()
        return instance
