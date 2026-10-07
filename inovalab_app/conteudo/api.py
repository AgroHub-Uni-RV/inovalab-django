from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ModelViewSet

from inovalab_app.adapters.host import is_business_admin
from inovalab_app.conteudo.models import LocalBanner
from inovalab_app.conteudo.selectors import published_banners, visible_banners
from inovalab_app.conteudo.serializers import BannerSerializer, DeleteBannerSerializer, PublicBannerSerializer
from inovalab_app.conteudo.services import BannerConflict, delete_banner


class IsBannerAdmin(BasePermission):
    message = 'Somente administradores do laboratório podem administrar banners.'

    def has_permission(self, request, view):
        return is_business_admin(request.user)


class BannerPagination(PageNumberPagination):
    page_size = 25


class NoStoreMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class BannerViewSet(NoStoreMixin, ModelViewSet):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsBannerAdmin]
    parser_classes = [JSONParser, MultiPartParser]
    renderer_classes = [JSONRenderer]
    pagination_class = BannerPagination
    serializer_class = BannerSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return visible_banners(self.request.user)

    def handle_exception(self, exc):
        if isinstance(exc, BannerConflict):
            return Response({'detail': str(exc), 'code': 'versao_desatualizada'}, status=409)
        return super().handle_exception(exc)

    def destroy(self, request, *args, **kwargs):
        banner = self.get_object()
        serializer = DeleteBannerSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        delete_banner(actor=request.user, banner_id=banner.pk, expected_version=serializer.validated_data['versao'])
        return Response(status=204)


class PublicBannerListView(NoStoreMixin, ListAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]
    pagination_class = BannerPagination
    serializer_class = PublicBannerSerializer

    def get_queryset(self):
        local = self.request.query_params.get('local')
        if local not in LocalBanner.values:
            raise ValidationError({'local': 'Informe home ou sobre.'})
        return published_banners(local)
