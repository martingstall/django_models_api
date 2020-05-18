from django.db.models import Q, F

from .base import Base

# Rows to return if length param not set
DEFAULT_LENGTH = 200

class GetData(Base):

    def get_objects(self):
        objects = self.model_path.objects.all()

        if self.data_fields:
            m2m_relationships = []
            fk_relationships = []
            fields = []
            # Data for the param 'data_fields' is passed as comma delimited
            for field in self.data_fields.split(','):
                query_field = field.replace(".", "__")
                if query_field not in fields:
                    fields.append(query_field)

                split_field = field.split('.')

                # Find any relationships, create dictionaries and store respective fields in them
                for num in range(0, len(split_field)):
                    if len(split_field) == 1:
                        if query_field not in m2m_relationships and split_field[0] in self.__known_m2m():
                            m2m_relationships.append(query_field)

                    elif len(split_field) == 2:
                        relationship = split_field[0]
                        if relationship not in fk_relationships and split_field[1] not in self.__known_m2m():
                            fk_relationships.append(relationship)

                        if query_field not in m2m_relationships and split_field[1] in self.__known_m2m():
                            m2m_relationships.append(query_field)

                    elif len(split_field) == 3:
                        relationship = split_field[0] + "__" + split_field[1]
                        if relationship not in fk_relationships and split_field[2] not in self.__known_m2m():
                            fk_relationships.append(relationship)

                        if query_field not in m2m_relationships and split_field[2] in self.__known_m2m():
                            m2m_relationships.append(query_field)

            for x in m2m_relationships:
                objects = objects.prefetch_related(str(x))

            # Seems faster than only() below
            for x in fk_relationships:
                objects = objects.select_related(str(x))

            """
            for x in fields:
                if x != "":
                    objects = objects.values(str(x))
                #objects = objects.only(str(x))
            """

        fatal_error = None

        ids = self.request.GET.getlist('ids')
        if ids:
            objects = objects.filter(pk__in=ids)

        model = self.model_path()
        filter_by_get_request = getattr(model, "filter_by_get_request", None)
        if callable(filter_by_get_request):
            try:
                objects = model.filter_by_get_request(self.request, objects)
            except Exception as e:
                objects = None
                fatal_error = {
                    'method': 'filter_by_get_request()',
                    'reason': str(e)
                }

        if not fatal_error:
            # Uses datatables inline search
            # inlineSearchString = self.request.GET.get('search[value]', '')

            # Uses our custom inline search
            inlineSearchString = self.request.GET.get('inline_search', '')

            if inlineSearchString and inlineSearchString != "":
                objects = self._or_inline_search(objects, inlineSearchString)

            # Deprecated and replaced with async call to django_models_api > api_getcount()
            #self.total = objects.count()
            self.total = 100000000000000
            self.start = self._set_start()
            self.length = self._set_length()
            self.draw = self._set_draw()

            if self.request.GET.get('order_by'):
                objects = self.order_by_get(objects)
            else:
                objects = self.order_by_using_datatables(objects)

            if self.request.GET.get('distinct') == "true":
                objects = objects.distinct()

            if self.length is not None and self.length > 0:
                objects = objects[self.start: (self.start + self.length)]

        return objects, fatal_error

    def order_by_get(self, objects):
        """
        Set by passing GET params
        order_by = column name
        order_dir = direction (asc, desc)

        :param objects:
        :return:
        """
        if not self.request.GET.get('order_dir') or self.request.GET.get('order_dir') == 'asc':
            objects = objects.order_by(F(str(self.request.GET.get('order_by'))).asc(nulls_last=True))
        elif self.request.GET.get('order_dir') == 'desc':
            objects = objects.order_by(F(str(self.request.GET.get('order_by'))).desc(nulls_last=True))

        return objects

    def order_by_using_datatables(self, objects):
        """
        Set by datatables column definitions (https://datatables.net/)

        :param objects:
        :return:
        """
        orderByIndex = self.request.GET.get('order[0][column]', None)
        if orderByIndex is not None:
            orderByKey = 'columns[' + orderByIndex + ']'
            orderByColumnName = self.request.GET.get(orderByKey + '[name]', '')
            orderByDirection = self.request.GET.get('order[0][dir]', 'asc')
        else:
            orderByDirection = None
            orderByColumnName = None

        if orderByDirection == "asc":
            objects = objects.order_by(F(orderByColumnName).asc(nulls_last=True))
        elif orderByDirection == "desc":
            objects = objects.order_by(F(orderByColumnName).desc(nulls_last=True))

        return objects

    def _create_datatables_order_by(self, index):
        """
        DEPRECATED

        :param index:
        :return:
        """
        orderByIndex = self.request.GET.get('order[' + str(index) + '][column]', None)

        if orderByIndex is not None:
            orderByKey = 'columns[' + orderByIndex + ']'
            orderByColumnName = self.request.GET.get(orderByKey + '[name]', '')
            orderByDirection = self.request.GET.get('order[' + str(index) + '][dir]', '1')
            if orderByDirection == 'desc':
                orderByColumnName = '-' + str(orderByColumnName)
        else:
            orderByDirection = None
            orderByColumnName = None

        return orderByDirection, orderByColumnName

    def _or_inline_search(self, objects, search_string):
        """
        Queries on "or" Fields are passed in the ajax
        URL via jQuery function listFieldNames()

        @param objects:
        @type objects:
        @param search_string:
        @type search_string:
        @return:
        @rtype:
        """
        qs = Q()

        try:
            for field in self.field_names.split(','):
                if field == "":
                    continue

                kwarg = {'{0}__icontains'.format(field): search_string}
                qs = qs | Q(**kwarg)
        except Exception as e:
            print(e)
            pass

        return objects.filter(qs)

    def _and_inline_search_kwargs(self, objects, search_string):
        """
        Queries on "and" (not currently in use and we'd want logic
        to use this OR _or_inline_search()).
        Fields are passed in the ajax URL via jQuery
        function listFieldNames().

        @param objects:
        @type objects:
        @param search_string:
        @type search_string:
        @return:
        @rtype:
        """
        self.inline_kwargs = {}

        try:
            for field in self.field_names.split(','):
                if field == "":
                    continue

                kwarg = {'{0}__icontains'.format(field): search_string}
                self.inline_kwargs.update(kwarg)
        except Exception as e:
            print(e)
            pass

        return objects.filter(**self.inline_kwargs)

    def _set_length(self):
        """
        How many should we return

        @return:
        @rtype:
        """
        length = self.request.GET.get('length', None)
        if length == "all":
            length = None
        elif length:
            length = int(length)
        else:
            length = DEFAULT_LENGTH

        return length

    def _set_start(self):
        """
        Database offset

        @return:
        @rtype:
        """
        start = self.request.GET.get('start', None)
        if start:
            start = int(start)
        else:
            start = 0

        return start

    def _set_draw(self):
        """
        Used in datatables (https://datatables.net/)

        @return:
        @rtype:
        """
        draw = self.request.GET.get('draw', None)
        if draw:
            draw = int(draw)
        else:
            draw = 1

        return draw

    def response(self, serializer):
        """
        """
        response = {
            'data': serializer.data,
            'recordsTotal': self.total,
            'recordsFiltered': self.total,
            'recordsDisplayed': self.length,
            'draw': self.draw
        }

        return response

    def __known_m2m(self):
        """
        Can we programmatically determine these?

        @return:
        @rtype:
        """
        fields = [
            'contextual_category',
            'secondary_contextual_category_filter_set',
            'ad_size_filter_set',
            'device_filter_set',
            'app_id_set',
            'sub_formats',
            'ad_format'
        ]

        return fields
