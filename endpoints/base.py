import importlib
from django.apps import apps

from rest_framework import serializers
from rest_framework.utils.field_mapping import get_nested_relation_kwargs

# Rows to return if length param not set
DEFAULT_LENGTH = 200

class Base:

    def __init__(self, request, model):
        """
        TBD...

        :param request:
        :param model:
        """
        self.request = request
        try:
            self.user = SMPUser.objects.get(user_id=self.request.auth.user_id)
        except:
            self.user = SMPUser.objects.get(user=self.request.user)

        self.field_names = self.request.GET.get('fieldnames')
        self.data_fields = self.request.GET.get('data_fields')
        self.set_fields = None
        self.model = model
        self.model_path = apps.get_model('smp', self.model)
        self.set_depth = 0

        self.verify_user()

    def serialize_model(self):
        """
        TBD...

        :return:
        """
        # Sets depth of the return. This will be overriden if the param 'data_fields' is set
        if self.request.GET.get('depth'):
            self.set_depth = int(self.request.GET.get('depth'))

        if self.data_fields:
            self.set_fields = []
            related_fields = {}

            # Data for the param 'data_fields' is passed as comma delimited
            for field in self.data_fields.split(','):
                split_field = field.split('.')

                # Overrides the 'depth' param if previously set
                if len(split_field) > self.set_depth:
                    self.set_depth = len(split_field)

                # Sets the base model fields to include
                if split_field[0] not in self.set_fields and split_field[0] != '':
                    self.set_fields.append(split_field[0])

                # Find any relationships, create dictionaries and store respective fields in them
                for num in range(0, len(split_field)):
                    try:
                        dict_key = str(split_field[num])
                        value = str(split_field[num+1])

                        # If related field hasn't been logged yet do so here
                        if related_fields.get(dict_key) is None:
                            related_fields[dict_key] = []

                        # If related model's field has been logged yet do so here
                        if value not in related_fields.get(dict_key):
                            related_fields.get(dict_key).append(value)
                    except Exception:
                        continue

        class serializeModel(serializers.ModelSerializer):
            if self.data_fields and ',active' in self.data_fields:
                active = serializers.CharField()

            def build_nested_field(self, field_name, relation_info, nested_depth):
                nested_fields = None

                try:
                    relation = str(relation_info.model_field)
                    relation = relation.split('.')
                    # Last index will be the related field (fk, or m2m) from the base model
                    nested_fields = related_fields.get(relation[2])

                    # Get and add the primary key
                    for field in relation_info.related_model._meta.fields:
                        if field.primary_key:
                            nested_fields.append(field.name)

                except Exception as e:
                    pass

                class DMApiNestedSerializer(serializeModel):
                    class Meta:
                        model = relation_info.related_model
                        depth = nested_depth - 1
                        if nested_fields is not None:
                            fields = nested_fields
                        else:
                            fields = '__all__'

                field_class = DMApiNestedSerializer
                field_kwargs = get_nested_relation_kwargs(relation_info)
                return field_class, field_kwargs

            class Meta:
                model = self.model_path
                depth = self.set_depth

                if self.set_fields is not None:
                    # Get and add the primary key
                    for field in model._meta.fields:
                        if field.primary_key:
                            self.set_fields.append(field.name)

                    fields = self.set_fields
                else:
                    fields = '__all__'

        return serializeModel

    def verify_user(self):
        """
        "Admin" level users have access to everything

        :return: Boolean
        """
        verified = False
        if self.user.role.role_name == "Admin":
            verified = True

        return verified
