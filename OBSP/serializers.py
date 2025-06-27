from rest_framework import serializers
from .models import OBSPTemplate, OBSPLevel, OBSPField, OBSPResponse

class OBSPLevelSerializer(serializers.ModelSerializer):
    """Serializer for OBSP levels"""
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    
    class Meta:
        model = OBSPLevel
        fields = [
            'id', 'level', 'level_display', 'name', 'price', 'duration', 
            'features', 'deliverables', 'is_active', 'order'
        ]

class OBSPTemplateSerializer(serializers.ModelSerializer):
    """Serializer for OBSP template with levels"""
    levels = OBSPLevelSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    industry_display = serializers.CharField(source='get_industry_display', read_only=True)
    
    class Meta:
        model = OBSPTemplate
        fields = [
            'id', 'title', 'category', 'category_display', 'industry', 'industry_display',
            'description', 'base_price', 'currency', 'is_active', 'levels',
            'created_at', 'updated_at'
        ]

class OBSPFieldSerializer(serializers.ModelSerializer):
    """Serializer for OBSP fields"""
    field_type_display = serializers.CharField(source='get_field_type_display', read_only=True)
    visibility_rule_display = serializers.CharField(source='get_visibility_rule_display', read_only=True)
    phase_display = serializers.CharField(source='get_phase_display_name', read_only=True)
    phase_description = serializers.CharField(source='get_phase_description', read_only=True)
    
    class Meta:
        model = OBSPField
        fields = [
            'id', 'field_type', 'field_type_display', 'label', 'placeholder', 
            'help_text', 'is_required', 'has_price_impact', 'price_impact', 
            'order', 'options', 'visibility_rule', 'visibility_rule_display',
            'phase', 'phase_display', 'phase_description'
        ]

class OBSPTemplateDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for OBSP template with levels and fields"""
    levels = OBSPLevelSerializer(many=True, read_only=True)
    fields = OBSPFieldSerializer(many=True, read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    industry_display = serializers.CharField(source='get_industry_display', read_only=True)
    
    class Meta:
        model = OBSPTemplate
        fields = [
            'id', 'title', 'category', 'category_display', 'industry', 'industry_display',
            'description', 'base_price', 'currency', 'is_active', 'levels', 'fields',
            'created_at', 'updated_at'
        ]

class OBSPTemplateCreateSerializer(serializers.ModelSerializer):
    fields = OBSPFieldSerializer(many=True)
    
    class Meta:
        model = OBSPTemplate
        fields = '__all__'
    
    def create(self, validated_data):
        fields_data = validated_data.pop('fields', [])
        template = OBSPTemplate.objects.create(**validated_data)
        
        for field_data in fields_data:
            OBSPField.objects.create(template=template, **field_data)
        
        return template

class OBSPResponseSerializer(serializers.ModelSerializer):
    template_title = serializers.CharField(source='template.title', read_only=True)
    client_name = serializers.CharField(source='client.username', read_only=True)
    
    class Meta:
        model = OBSPResponse
        fields = '__all__'