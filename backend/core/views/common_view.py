from rest_framework import viewsets, serializers, permissions
from core.models import Common

class CommonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Common
        fields = '__all__'

class CommonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    공통 코드 조회 API
    Query Parameter:
    - top_code: 그룹 코드로 필터링 (예: /api/core/commons/?top_code=JOB_ROLE)
    """
    permission_classes = [permissions.AllowAny]  # 모든 사용자가 인증 없이 API를 호출할 수 있도록 권한을 허용함
    queryset = Common.objects.all()
    serializer_class = CommonSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(use_yn='Y')
        top_code = self.request.query_params.get('top_code')
        if top_code:
            queryset = queryset.filter(top_code=top_code)
        return queryset
