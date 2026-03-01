"""
Middleware for handling multi-school context in requests.
Sets the current school based on session or user preferences.
"""
from django.utils.deprecation import MiddlewareMixin
from .models import School
from django.db.models import Q


class SchoolContextMiddleware(MiddlewareMixin):
    """
    Adds school context to each request.
    Stores current school in request.school for easy access throughout views.
    """
    
    def process_request(self, request):
        """
        Process each request to set the school context.
        Priority: session > user default > first active school
        """
        school = None
        
        # Try to get school from session
        if hasattr(request, 'session'):
            school_id = request.session.get('current_school_id')
            if school_id:
                try:
                    school = School.objects.select_related('organization').get(
                        id=school_id,
                        is_active=True
                    )
                except School.DoesNotExist:
                    # Clear invalid school from session
                    request.session.pop('current_school_id', None)
        
        # Try to get from user's profile if authenticated
        if not school and request.user.is_authenticated:
            # Check if user has a default school preference
            if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'default_school'):
                school = request.user.profile.default_school
                if school and school.is_active:
                    # Store in session for future requests
                    request.session['current_school_id'] = school.id
        
        # If a forced identifier is configured, ignore session/user prefs
        from django.conf import settings
        if settings.FORCE_SCHOOL_IDENTIFIER:
            # try to match by name or code
            forced = School.objects.filter(
                Q(school_name__icontains=settings.FORCE_SCHOOL_IDENTIFIER) |
                Q(school_code__icontains=settings.FORCE_SCHOOL_IDENTIFIER),
                is_active=True
            ).select_related('organization').first()
            if forced:
                school = forced
                if hasattr(request, 'session'):
                    request.session['current_school_id'] = school.id
        # Fallback to first active school
        if not school:
            school = School.objects.select_related('organization').filter(is_active=True).first()
            if school and hasattr(request, 'session'):
                request.session['current_school_id'] = school.id
        
        # Attach school to request
        request.school = school
        
        # Also attach organization if school exists
        request.organization = school.organization if school else None
        
        # expose forced identifier for templates
        from django.conf import settings
        request.force_school_identifier = settings.FORCE_SCHOOL_IDENTIFIER
        
        return None


class SchoolAccessMiddleware(MiddlewareMixin):
    """
    Middleware to enforce school-level access control.
    Ensures users can only access data from schools they're authorized for.
    """
    
    def process_request(self, request):
        """
        Verify user has access to the current school context.
        Superusers and staff bypass this check.
        """
        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return None
        
        # Superusers and staff can access all schools
        if request.user.is_superuser or request.user.is_staff:
            return None
        
        # Get current school from request (set by SchoolContextMiddleware)
        current_school = getattr(request, 'school', None)
        
        if not current_school:
            return None
        
        # Check if user has access to this school
        # This can be customized based on your access control requirements
        user_schools = self._get_user_schools(request.user)
        
        if current_school not in user_schools:
            # User doesn't have access to this school
            # Switch to their first accessible school
            if user_schools:
                first_school = user_schools[0]
                request.school = first_school
                request.organization = first_school.organization
                if hasattr(request, 'session'):
                    request.session['current_school_id'] = first_school.id
        
        return None
    
    def _get_user_schools(self, user):
        """
        Get list of schools the user has access to.
        Override this method to implement custom access logic.
        """
        from .models import SchoolAdmin
        
        # Check if user is a school admin
        admin_schools = School.objects.filter(
            administrators__user=user,
            administrators__is_active=True,
            is_active=True
        ).distinct()
        
        if admin_schools.exists():
            return list(admin_schools)
        
        # Check if user is a teacher
        if hasattr(user, 'teacher_profile'):
            teacher_school = getattr(user.teacher_profile, 'school', None)
            if teacher_school:
                return [teacher_school]
        
        # Check if user is a student
        if hasattr(user, 'student_profile'):
            student_school = getattr(user.student_profile, 'school', None)
            if student_school:
                return [student_school]
        
        # Default: return all active schools if no specific access found
        return list(School.objects.filter(is_active=True))
