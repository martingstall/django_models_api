import hashlib
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse, StreamingHttpResponse

from rest_framework.decorators import api_view
from rest_framework.settings import api_settings
from rest_framework.renderers import JSONRenderer
from rest_framework_csv.renderers import CSVRenderer, CSVStreamingRenderer
from rest_framework.parsers import JSONParser

from .endpoints import Base, GetData, PutObject, PostObject



class JSONResponse(HttpResponse):
    """
    An HttpResponse that renders its content into JSON.
    """
    def __init__(self, data, **kwargs):
        content = JSONRenderer().render(data)

        kwargs['content_type'] = 'application/json'
        super(JSONResponse, self).__init__(content, **kwargs)


class CSVResponse(HttpResponse):
    def __init__(self, data, **kwargs):
        content = CSVRenderer().render(data)

        kwargs['content_type'] = 'text/csv'
        super(CSVResponse, self).__init__(content, **kwargs)


@login_required
def api_getcount(request, endpoint):
    """
    Postgres count() is very slow so we have a separate API call to get counts to the UI.
    This is used primarily for DataTables (datatables.js > overridePagination).

    :param request:
    :param endpoint: Django model name (case sensitive)
    :return:
    """
    model_serializer = Base(request, endpoint)

    objects = model_serializer.model_path.objects
    model = model_serializer.model_path()
    filter_by_get_request = getattr(model, "filter_by_get_request", None)
    if callable(filter_by_get_request):
        try:
            objects = model.filter_by_get_request(request, objects)
        except Exception as e:
            objects = objects.all()

    count = objects.count()

    return JSONResponse({'count': count})


@api_view(['POST','GET','PUT'])
@login_required
def api_getlist(request, endpoint):
    """
    Method name is now misleading as inserts and updates can now be performed.

    Variable 'recordsTotal' handled by api_getcount().

    :param request:
    :param endpoint: Django model name (case sensitive)
    :return:
    """
    model = endpoint
    return_as = request.GET.get('return_as', 'json')

    if request.method == 'GET':
        model_serializer = GetData(request, model)
        """
        if not model_serializer.verify_user():
            return JSONResponse(
                {
                    "response": 403,
                    "msg": "Permission denied"
                }
            )
        """

        objects, fatal_error = model_serializer.get_objects()

        if not fatal_error:
            serialized = model_serializer.serialize_model()(objects, many=True, context={'request': request})
            response = model_serializer.response(serialized)
        else:
            response = {
                'data': 0,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'recordsDisplayed': 0,
                'draw': 0,
                'error': fatal_error
            }

        if return_as == 'csv':
            filename = "Download"
            renderer = CSVStreamingRenderer()
            response = StreamingHttpResponse(
                renderer.render(response.get('data')),
                content_type='text/csv'
            )
            response['Content-Disposition'] = 'attachment; filename="{0}.csv"'.format(filename)

            return response
        else:
            return JSONResponse(response)

    elif request.method == 'PUT':
        model_serializer = PutObject(request, model)
        if not model_serializer.verify_user():
            return JSONResponse(
                {
                    "response": 403,
                    "msg": "Permission denied"
                }
            )

        try:
            model_serializer.get_object(request.data.get('id'))
        except:
            return JSONResponse(
                {
                    "response": 400,
                    "msg": "Requested object was not found"
                }
            )

        serializer = model_serializer.serialize_model()(model_serializer.object, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            return JSONResponse(
                {
                    "response": 200,
                    "msg": "{0} object saved".format(endpoint)
                }
            )

        return JSONResponse(
            {
                "response": 400,
                "errors": serializer.errors,
                "msg": "{0} object was not saved".format(endpoint)
            }
        )

    elif request.method == 'POST':
        model_serializer = PostObject(request, model)
        if not model_serializer.verify_user():
            return JSONResponse(
                {
                    "response": 403,
                    "msg": "Permission denied"
                }
            )

        serializer = model_serializer.serialize_model()(data=request.data)
        if serializer.is_valid():
            serializer.save()

            return JSONResponse(
                {
                    "response": 200,
                    "msg": "{0} object created".format(endpoint)
                }
            )

        return JSONResponse(
            {
                "response": 400,
                "errors": serializer.errors,
                "msg": "{0} object was not created".format(endpoint)
            }
        )
