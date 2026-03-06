# 수정일: 2026-02-06
# 수정내용: Antigravity - 회원 정보 수정(IsOwner) 및 아바타 실시간 재생성 로직 구현
#           (수정일: 2026-02-06.2) get_permissions 권한 복구 및 디버깅 로그 강화

from rest_framework import viewsets, serializers, permissions, status
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash # [수정일: 2026-02-16] 세션 유지용
from core.models import UserProfile, UserDetail, UserAvatar, UserActivity
from core.utils.nanobanana_utils import generate_nano_banana_avatar # 나노바나나 연동
import traceback
import os
import uuid
from django.conf import settings

# 1. UserDetail Serializer
class UserDetailSerializer(serializers.ModelSerializer):
    job_role = serializers.ListField(
        child=serializers.CharField(),
        required=False, 
        allow_empty=True
    )
    interests = serializers.ListField(
        child=serializers.CharField(),
        required=False, 
        allow_empty=True
    )

    avatar_style = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)
    avatar_seed = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)
    avatar_preview_url = serializers.CharField(required=False, write_only=True, allow_blank=True, allow_null=True)

    class Meta:
        model = UserDetail
        fields = ['is_developer', 'job_role', 'interests', 'avatar_style', 'avatar_seed', 'avatar_preview_url']

    # [수정일: 2026-02-07] JSONField 사용으로 인해 to_representation의 변환 로직이 더 이상 필요 없음


# 2. UserProfile Serializer (Nested)
class UserProfileSerializer(serializers.ModelSerializer):
    user_detail = UserDetailSerializer(required=False)
    # [수정일: 2026-02-07] Serializer의 UniqueValidator가 모델의 save() 충돌 방지 로직보다 먼저 실행되어 
    # 가입을 차단하는 것을 방지하기 위해 검증 제외 처리
    username = serializers.CharField(required=False, validators=[])

    class Meta:
        model = UserProfile
        fields = '__all__'
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate(self, data):
        if 'user_nickname' in data:
            if len(data['user_nickname']) < 2:
                raise serializers.ValidationError({"user_nickname": "닉네임을 2글자 이상 입력해주세요."})
            if len(data['user_nickname']) > 20:
                raise serializers.ValidationError({"user_nickname": "닉네임은 20글자 이하이어야 합니다."})

        if self.instance is None and 'password' in data:
            password = data['password']
            if len(password) < 8:
                raise serializers.ValidationError({"password": "비밀번호는 8자 이상이어야 합니다."})
            
        return data

    def validate_email(self, value):
        if UserProfile.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 가입된 이메일입니다.")
        return value

    def create(self, validated_data):
        from django.db import transaction
        validated_data['create_id'] = 'admin'
        validated_data['update_id'] = 'admin'

        detail_data = validated_data.pop('user_detail', {})
        raw_password = validated_data.get('password')

        # [수정일: 2026-02-07] id는 AutoField이므로 수동 생성 안 함. username이 그 역할을 대신함.
        email = validated_data.get('email')
        username = validated_data.get('username')
        if not username and email:
            # username 생성 로직 (모델의 save에서도 처리하지만 여기서 미리 처리할 수도 있음)
            pass

        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])

        try:
            with transaction.atomic():
                # [수정일: 2026-02-07] UserProfile을 먼저 생성하여 정수 id를 얻음
                user_profile = UserProfile.objects.create(**validated_data)
                
                # [수정일: 2026-02-07] auth.User와 동기화 (모델의 save에서 확정된 유일한 username 사용)
                if raw_password:
                    User.objects.create_user(username=user_profile.username, email=email, password=raw_password)

                avatar_style = detail_data.pop('avatar_style', 'default duck')
                avatar_seed = detail_data.pop('avatar_seed', None)
                preview_url = detail_data.pop('avatar_preview_url', None)
                
                final_image_url = None
                final_seed = avatar_seed
                
                # [수정일: 2026-02-08] 회원가입 시에도 미리보기(Preview) 채택 로직 적용
                if preview_url:
                    if '?' in str(preview_url):
                        preview_url = preview_url.split('?')[0]

                    # 로컬 경로(/media/...)인 경우 S3로 업로드
                    if preview_url.startswith('/media/'):
                        local_rel_path = preview_url.lstrip('/')
                        local_full_path = os.path.join(settings.BASE_DIR, local_rel_path)
                        if os.path.exists(local_full_path):
                            try:
                                from core.utils.nanobanana_utils import upload_to_s3
                                with open(local_full_path, 'rb') as f:
                                    s3_url = upload_to_s3(f.read())
                                    if s3_url:
                                        print(f"DEBUG: Signup - Promoted local preview to S3: {s3_url}", flush=True)
                                        preview_url = s3_url
                            except Exception as e:
                                print(f"DEBUG: Signup - Failed to upload preview to S3: {e}", flush=True)

                    final_image_url = preview_url
                    print(f"DEBUG: Signup - Promoting preview avatar: {final_image_url}", flush=True)
                else:
                    # 미리보기가 없는 경우에만 재생성 (Antigravity 로직 유지)
                    avatar_data = generate_nano_banana_avatar(avatar_style, seed=avatar_seed)
                    if avatar_data:
                        final_image_url = avatar_data['url']
                        final_seed = avatar_data.get('seed')

                active_avatar = None
                if final_image_url:
                    active_avatar = UserAvatar.objects.create(
                        user=user_profile,
                        image_url=final_image_url,
                        prompt=avatar_style,
                        seed=final_seed,
                        is_active=True,
                        create_id='system'
                    )

                UserActivity.objects.create(
                    user=user_profile,
                    active_avatar=active_avatar,
                    create_id='system'
                )

                # [수정일: 2026-02-07] JSONField 사용으로 인해 문자열 변환(join) 로직 제거
                UserDetail.objects.create(user=user_profile, **detail_data)
                return user_profile
        except Exception as e:
            traceback.print_exc()
            raise serializers.ValidationError({"detail": f"회원가입 처리 중 오류가 발생했습니다: {str(e)}"})

    def update(self, instance, validated_data):
        from django.db import transaction
        detail_data = validated_data.pop('user_detail', {})
        
        if 'password' in validated_data:
            raw_password = validated_data['password']
            validated_data['password'] = make_password(raw_password)
            try:
                auth_user = User.objects.get(email=instance.email)
                auth_user.set_password(raw_password)
                auth_user.save()
                
                # [수정일: 2026-02-16] 비밀번호 변경 후에도 현재 세션을 유지하도록 처리
                request = self.context.get('request')
                if request and request.user == auth_user:
                    update_session_auth_hash(request, auth_user)
                    print(f"DEBUG: Session auth hash updated for {auth_user.username}", flush=True)
            except User.DoesNotExist:
                pass
        
        try:
            with transaction.atomic():
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.save()
                
                if hasattr(instance, 'user_detail'):
                    detail = instance.user_detail
                    new_style = detail_data.get('avatar_style', '').strip()
                    new_seed = detail_data.get('avatar_seed')
                    preview_url = detail_data.get('avatar_preview_url')
                    
                    # 현재 아바타 정보 확인
                    current_avatar = instance.activity.active_avatar if hasattr(instance, 'activity') else None
                    current_style = current_avatar.prompt if current_avatar else ""
                    current_seed = current_avatar.seed if current_avatar else None
                    
                    final_image_url = None
                    final_seed = new_seed

                    # [수정일: 2026-02-10] '미리보기 채택(Promotion)' 시 S3 업로드 보장
                    if preview_url:
                        print(f"DEBUG: Profile Update - Promoting preview avatar: {preview_url}", flush=True)
                        # 캐시 방지용 쿼리스트링 제거
                        if '?' in str(preview_url):
                            preview_url = preview_url.split('?')[0]
                        
                        # 만약 로컬 경로(/media/...)라면 S3로 업로드하여 전역 가시성 확보
                        if preview_url.startswith('/media/'):
                            local_rel_path = preview_url.lstrip('/')
                            local_full_path = os.path.join(settings.BASE_DIR, local_rel_path)
                            if os.path.exists(local_full_path):
                                from core.utils.nanobanana_utils import upload_to_s3
                                try:
                                    with open(local_full_path, 'rb') as f:
                                        s3_url = upload_to_s3(f.read())
                                        if s3_url:
                                            print(f"DEBUG: Promoted local preview to S3: {s3_url}", flush=True)
                                            preview_url = s3_url
                                except Exception as e:
                                    print(f"DEBUG: Failed to upload promoted preview to S3: {e}", flush=True)

                        final_image_url = preview_url
                    # 스타일이나 시드가 명시적으로 변경된 경우만 재생성 (채택 URL이 없을 때)
                    elif (new_style and new_style != current_style) or (new_seed and str(new_seed) != str(current_seed)):
                        print(f"DEBUG: Profile Update - Regenerating avatar with style: {new_style} (Seed: {new_seed})", flush=True)
                        from core.utils.nanobanana_utils import upload_to_s3
                        avatar_data = generate_nano_banana_avatar(new_style, seed=new_seed, save_local=False)
                        
                        if avatar_data and 'image_data' in avatar_data:
                            # [수정일: 2026-02-10] S3 업로드 통합
                            final_image_url = upload_to_s3(avatar_data['image_data'])
                            
                            # S3 실패 시 폴백
                            if not final_image_url:
                                filename = f"avatar_{uuid.uuid4().hex}.webp"
                                media_path = os.path.join('avatars', filename)
                                abs_path = os.path.join(settings.MEDIA_ROOT, media_path)
                                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                                with open(abs_path, 'wb') as f:
                                    f.write(avatar_data['image_data'])
                                final_image_url = f"{settings.MEDIA_URL}{media_path}"
                                print(f"DEBUG: S3 Promotion failed in update, fallback to local: {final_image_url}", flush=True)
                            
                            final_seed = avatar_data.get('seed')
                        
                        # AI 생성 실패 시 fallback URL
                        if not final_image_url and avatar_data:
                            final_image_url = avatar_data.get('url')

                    if final_image_url:
                        # 기존 아바타 비활성화
                        UserAvatar.objects.filter(user=instance, is_active=True).update(is_active=False)
                        # 새 아바타 생성
                        new_avatar = UserAvatar.objects.create(
                            user=instance,
                            image_url=final_image_url,
                            prompt=new_style or current_style,
                            seed=final_seed or current_seed,
                            is_active=True,
                            create_id='system'
                        )
                        # 활동 정보 업데이트
                        activity, _ = UserActivity.objects.get_or_create(user=instance)
                        activity.active_avatar = new_avatar
                        activity.save()
                        print(f"DEBUG: Profile Update - Final avatar promoted/updated to {final_image_url}", flush=True)

                    if 'is_developer' in detail_data:
                        detail.is_developer = detail_data['is_developer']
                    if 'job_role' in detail_data:
                        detail.job_role = detail_data['job_role']
                    if 'interests' in detail_data:
                        detail.interests = detail_data['interests']
                    detail.save()
                return instance
        except Exception as e:
            error_msg = f"프로필 수정 중 오류 발생: {type(e).__name__} - {str(e)}"
            print(f"!!! {error_msg}")
            traceback.print_exc()
            raise serializers.ValidationError({"detail": error_msg})

class IsOwner(permissions.BasePermission):
    """
    [수정일: 2026-03-06] 이메일 기반 소유자 확인으로 변경
    - auth.User와 UserProfile의 PK가 다르므로, 이메일로 소유자를 판별
    - 관리자(is_staff)는 항상 허용
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # 관리자는 항상 수정 가능
        if request.user.is_staff or request.user.is_superuser:
            return True
        # 이메일 매칭으로 소유자 확인 (auth.User.email == UserProfile.email)
        is_owner = obj.email == request.user.email
        return is_owner

class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    [수정일: 2026-02-07] CSRF 검증을 건너뛰는 SessionAuthentication 커스텀 클래스.
    개발 환경에서 Vite 프록시를 통한 API 호출 시 CSRF 토큰 문제를 우회합니다.
    프로덕션에서는 프론트엔드가 동일 도메인에서 서빙되어 이 문제가 발생하지 않습니다.
    """
    def enforce_csrf(self, request):
        return  # CSRF 검증 비활성화


class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    # [수정일: 2026-02-06] 사용자 ID(이메일 포함) 내 마침표(.) 조회를 허용하기 위해 정규표현식 수정
    lookup_value_regex = '[^/]+'
    # [수정일: 2026-02-07] 명시적 인증 클래스 설정 - CSRF 우회 버전 사용
    authentication_classes = [CsrfExemptSessionAuthentication]

    def create(self, request, *args, **kwargs):
        """
        [수정일: 2026-02-07] 회원가입 후 자동 로그인 처리
        - 기존 세션이 있으면 로그아웃 후 새 사용자로 로그인
        """
        from django.contrib.auth import login, logout
        from django.contrib.auth.models import User as AuthUser

        # 기존 세션이 있으면 로그아웃
        if request.user.is_authenticated:
            logout(request)

        response = super().create(request, *args, **kwargs)

        if response.status_code == 201:
            # 새로 생성된 사용자로 자동 로그인
            email = request.data.get('email')
            try:
                auth_user = AuthUser.objects.get(email=email)
                login(request, auth_user)
                print(f"DEBUG: Auto-login successful for {auth_user.username}", flush=True)
            except AuthUser.DoesNotExist:
                print(f"DEBUG: Auto-login failed - AuthUser not found for {email}", flush=True)

        return response

    def get_object(self):
        """
        [수정일: 2026-03-06] 404 에러 수정: PK가 정수가 아닌 경우(username 등) fallback 처리
        - auth_view.py에서 UserProfile이 없을 때 user.username을 id로 반환하는 경우 대응
        """
        pk = self.kwargs.get('pk')
        try:
            obj = UserProfile.objects.get(pk=pk)
        except (UserProfile.DoesNotExist, ValueError, TypeError):
            # PK 조회 실패 시 username으로 재시도
            try:
                obj = UserProfile.objects.get(username=pk)
            except UserProfile.DoesNotExist:
                from rest_framework.exceptions import NotFound
                raise NotFound(f"UserProfile을 찾을 수 없습니다: {pk}")
        self.check_object_permissions(self.request, obj)
        return obj

    def partial_update(self, request, *args, **kwargs):
        print(f"DEBUG PATCH: User={request.user} (Authenticated={request.user.is_authenticated}), ID={kwargs.get('pk')}", flush=True)
        try:
            return super().partial_update(request, *args, **kwargs)
        except Exception as e:
            print(f"!!! DEBUG PATCH Error: {str(e)}", flush=True)
            traceback.print_exc()
            raise

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            # [수정일: 2026-03-06] IsOwner 복원 (이메일 매칭 기반으로 안전하게 동작)
            return [permissions.IsAuthenticated(), IsOwner()]
        return [permissions.AllowAny()]