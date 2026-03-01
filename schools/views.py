from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q, Sum
from .models import Organization, School, AcademicConfig, SchoolBranding, SchoolAdmin
from .forms import (
    OrganizationForm, SchoolForm, AcademicConfigForm, 
    SchoolBrandingForm, SchoolAdminForm
)


def is_superuser(user):
    """Check if user is superuser"""
    return user.is_superuser


@login_required
def organization_dashboard(request):
    """Dashboard for organization-level overview"""
    organizations = Organization.objects.annotate(
        school_count=Count('schools', filter=Q(schools__is_active=True))
    ).filter(is_active=True)
    
    # Total statistics across all organizations
    total_organizations = organizations.count()
    total_schools = School.objects.filter(is_active=True).count()
    
    # Get student count if Student model exists
    try:
        from students.models import Student
        total_students = Student.objects.filter(is_active=True).count()
    except:
        total_students = 0
    
    # Get teacher count if Teacher model exists
    try:
        from teachers.models import Teacher
        total_teachers = Teacher.objects.filter(is_active=True).count()
    except:
        total_teachers = 0
    
    context = {
        'organizations': organizations,
        'total_organizations': total_organizations,
        'total_schools': total_schools,
        'total_students': total_students,
        'total_teachers': total_teachers,
    }
    return render(request, 'schools/organization_dashboard.html', context)


@login_required
@user_passes_test(is_superuser)
def organization_list(request):
    """List all organizations"""
    organizations = Organization.objects.annotate(
        school_count=Count('schools', filter=Q(schools__is_active=True))
    ).filter(is_active=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        organizations = organizations.filter(
            Q(name__icontains=search_query) |
            Q(registration_number__icontains=search_query) |
            Q(organization_code__icontains=search_query)
        )
    
    context = {
        'organizations': organizations,
        'search_query': search_query,
    }
    return render(request, 'schools/organization_list.html', context)


@login_required
@user_passes_test(is_superuser)
def organization_create(request):
    """Create new organization"""
    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'Organization "{organization.name}" created successfully!')
            return redirect('schools:organization_detail', pk=organization.pk)
    else:
        form = OrganizationForm()
    
    context = {'form': form}
    return render(request, 'schools/organization_form.html', context)


@login_required
def organization_detail(request, pk):
    """View organization details"""
    organization = get_object_or_404(
        Organization.objects.annotate(
            school_count=Count('schools', filter=Q(schools__is_active=True))
        ),
        pk=pk
    )
    
    schools = organization.schools.filter(is_active=True)
    
    # Calculate total capacity and enrollment across all schools
    total_capacity = schools.aggregate(total=Sum('total_capacity'))['total'] or 0
    
    try:
        from students.models import Student
        total_enrollment = Student.objects.filter(
            school__organization=organization,
            is_active=True
        ).count()
    except:
        total_enrollment = 0
    
    context = {
        'organization': organization,
        'schools': schools,
        'total_capacity': total_capacity,
        'total_enrollment': total_enrollment,
    }
    return render(request, 'schools/organization_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def organization_update(request, pk):
    """Update organization details"""
    organization = get_object_or_404(Organization, pk=pk)
    
    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'Organization "{organization.name}" updated successfully!')
            return redirect('schools:organization_detail', pk=organization.pk)
    else:
        form = OrganizationForm(instance=organization)
    
    context = {'form': form, 'organization': organization}
    return render(request, 'schools/organization_form.html', context)


@login_required
def school_dashboard(request):
    """Dashboard for current school"""
    school = request.school
    
    if not school:
        messages.warning(request, 'No school context available.')
        return redirect('schools:school_list')
    
    # Get statistics
    try:
        from students.models import Student
        total_students = Student.objects.filter(school=school, is_active=True).count()
    except:
        total_students = 0
    
    try:
        from teachers.models import Teacher
        total_teachers = Teacher.objects.filter(school=school, is_active=True).count()
    except:
        total_teachers = 0
    
    # Get academic config
    try:
        academic_config = school.academic_config
    except:
        academic_config = None
    
    context = {
        'school': school,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'academic_config': academic_config,
        'enrollment_percentage': school.enrollment_percentage,
        'available_capacity': school.available_capacity,
    }
    return render(request, 'schools/school_dashboard.html', context)


@login_required
def school_list(request):
    """List all schools"""
    from django.conf import settings

    schools = School.objects.select_related('organization').filter(is_active=True)
    
    # enforce single-school mode if configured
    if settings.FORCE_SCHOOL_IDENTIFIER:
        schools = schools.filter(
            Q(school_name__icontains=settings.FORCE_SCHOOL_IDENTIFIER) |
            Q(school_code__icontains=settings.FORCE_SCHOOL_IDENTIFIER)
        )
        # skip other filters since there is only one school to show
        organization_id = None
        school_type = None
        search_query = ''
    else:
        # Filters
        organization_id = request.GET.get('organization')
        school_type = request.GET.get('school_type')
        search_query = request.GET.get('search', '')
    
    if organization_id:
        schools = schools.filter(organization_id=organization_id)
    
    if school_type:
        schools = schools.filter(school_type=school_type)
    
    if search_query:
        schools = schools.filter(
            Q(school_name__icontains=search_query) |
            Q(school_code__icontains=search_query) |
            Q(principal_name__icontains=search_query)
        )
    
    # Get organizations for filter dropdown
    organizations = Organization.objects.filter(is_active=True)
    
    context = {
        'schools': schools,
        'organizations': organizations,
        'search_query': search_query,
        'selected_organization': organization_id,
        'selected_school_type': school_type,
    }
    return render(request, 'schools/school_list.html', context)


@login_required
@user_passes_test(is_superuser)
def school_create(request):
    """Create new school"""
    if request.method == 'POST':
        form = SchoolForm(request.POST, request.FILES)
        if form.is_valid():
            school = form.save()
            
            # Create default academic config
            AcademicConfig.objects.create(
                school=school,
                current_academic_year='2024-2025',
                academic_year_start='2024-09-01',
                academic_year_end='2025-06-30'
            )
            
            # Create default branding
            SchoolBranding.objects.create(school=school)
            
            messages.success(request, f'School "{school.school_name}" created successfully!')
            return redirect('schools:school_detail', pk=school.pk)
    else:
        form = SchoolForm()
    
    context = {'form': form}
    return render(request, 'schools/school_form.html', context)


@login_required
def school_detail(request, pk):
    """View school details"""
    school = get_object_or_404(School.objects.select_related('organization'), pk=pk)
    
    # Get statistics
    try:
        from students.models import Student
        total_students = Student.objects.filter(school=school, is_active=True).count()
        recent_admissions = Student.objects.filter(school=school).order_by('-admission_date')[:5]
    except:
        total_students = 0
        recent_admissions = []
    
    try:
        from teachers.models import Teacher
        total_teachers = Teacher.objects.filter(school=school, is_active=True).count()
    except:
        total_teachers = 0
    
    # Get administrators
    administrators = school.administrators.select_related('user').filter(is_active=True)
    
    # Get academic config
    try:
        academic_config = school.academic_config
    except:
        academic_config = None
    
    context = {
        'school': school,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'recent_admissions': recent_admissions,
        'administrators': administrators,
        'academic_config': academic_config,
    }
    return render(request, 'schools/school_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def school_update(request, pk):
    """Update school details"""
    school = get_object_or_404(School, pk=pk)
    
    if request.method == 'POST':
        form = SchoolForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            school = form.save()
            messages.success(request, f'School "{school.school_name}" updated successfully!')
            return redirect('schools:school_detail', pk=school.pk)
    else:
        form = SchoolForm(instance=school)
    
    context = {'form': form, 'school': school}
    return render(request, 'schools/school_form.html', context)


@login_required
def school_switch(request, pk):
    """Switch current school context"""
    school = get_object_or_404(School, pk=pk, is_active=True)
    
    # Store in session
    request.session['current_school_id'] = school.id
    
    messages.success(request, f'Switched to {school.school_name}')
    return redirect('schools:school_dashboard')


@login_required
def academic_config_update(request, school_pk):
    """Update school academic configuration"""
    school = get_object_or_404(School, pk=school_pk)
    
    # Get or create academic config
    academic_config, created = AcademicConfig.objects.get_or_create(school=school)
    
    if request.method == 'POST':
        form = AcademicConfigForm(request.POST, instance=academic_config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Academic configuration updated successfully!')
            return redirect('schools:school_detail', pk=school.pk)
    else:
        form = AcademicConfigForm(instance=academic_config)
    
    context = {'form': form, 'school': school}
    return render(request, 'schools/academic_config_form.html', context)


@login_required
def branding_update(request, school_pk):
    """Update school branding"""
    school = get_object_or_404(School, pk=school_pk)
    
    # Get or create branding
    branding, created = SchoolBranding.objects.get_or_create(school=school)
    
    if request.method == 'POST':
        form = SchoolBrandingForm(request.POST, request.FILES, instance=branding)
        if form.is_valid():
            form.save()
            messages.success(request, 'School branding updated successfully!')
            return redirect('schools:school_detail', pk=school.pk)
    else:
        form = SchoolBrandingForm(instance=branding)
    
    context = {'form': form, 'school': school}
    return render(request, 'schools/branding_form.html', context)


@login_required
@user_passes_test(is_superuser)
def school_admin_create(request, school_pk):
    """Assign school administrator"""
    school = get_object_or_404(School, pk=school_pk)
    
    if request.method == 'POST':
        form = SchoolAdminForm(request.POST)
        if form.is_valid():
            school_admin = form.save(commit=False)
            school_admin.school = school
            school_admin.save()
            messages.success(request, 'School administrator assigned successfully!')
            return redirect('schools:school_detail', pk=school.pk)
    else:
        form = SchoolAdminForm()
    
    context = {'form': form, 'school': school}
    return render(request, 'schools/school_admin_form.html', context)


@login_required
@user_passes_test(is_superuser)
def school_admin_update(request, pk):
    """Update school administrator"""
    school_admin = get_object_or_404(SchoolAdmin, pk=pk)
    
    if request.method == 'POST':
        form = SchoolAdminForm(request.POST, instance=school_admin)
        if form.is_valid():
            form.save()
            messages.success(request, 'School administrator updated successfully!')
            return redirect('schools:school_detail', pk=school_admin.school.pk)
    else:
        form = SchoolAdminForm(instance=school_admin)
    
    context = {'form': form, 'school_admin': school_admin}
    return render(request, 'schools/school_admin_form.html', context)
