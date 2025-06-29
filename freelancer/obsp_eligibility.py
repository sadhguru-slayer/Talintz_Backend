from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from Profile.models import FreelancerProfile, FreelancerReview, Feedback
from OBSP.models import OBSPTemplate, OBSPCriteria, OBSPResponse
from core.models import Project, Skill
import json

def serialize_for_json(obj):
    """
    Convert objects to JSON-serializable format
    Handles Decimal, datetime, and other non-serializable types
    """
    import json
    from decimal import Decimal
    from datetime import datetime, date
    from django.utils import timezone
    
    def _convert(value):
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, (datetime, date)):
            return value.isoformat()
        elif isinstance(value, timezone.datetime):
            return value.isoformat()
        elif isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_convert(item) for item in value]
        elif isinstance(value, set):
            return list(value)
        else:
            return value
    
    return _convert(obj)

class OBSPEligibilityEvaluator:
    """
    Evaluates freelancer eligibility for OBSP levels based on criteria
    """
    
    def __init__(self, freelancer, obsp_template, level):
        self.freelancer = freelancer
        self.freelancer_profile = freelancer.freelancer_profile
        self.obsp_template = obsp_template
        self.level = level
        self.criteria = OBSPCriteria.objects.get(
            template=obsp_template,
            level=level,
            is_active=True
        )
        self.evaluation_result = {}
    
    def evaluate_eligibility(self):
        """Main evaluation method"""
        try:
            self.evaluation_result = {
                'is_eligible': False,
                'overall_score': 0,
                'detailed_breakdown': {},
                'reasons': [],
                'proof': {},
                'level': self.level,
                'obsp_template': self.obsp_template.title,
                'evaluated_at': timezone.now().isoformat()
            }
            
            project_experience_score = self._evaluate_project_experience()
            skill_match_score = self._evaluate_skill_match()
            rating_score = self._evaluate_rating()
            deadline_compliance_score = self._evaluate_deadline_compliance()
            obsp_experience_score = self._evaluate_obsp_experience()
            
            weights = self.criteria.scoring_weights
            overall_score = (
                project_experience_score * weights.get('project_experience', 0.25) +
                skill_match_score * weights.get('skill_match', 0.35) +
                rating_score * weights.get('rating', 0.25) +
                deadline_compliance_score * weights.get('deadline_compliance', 0.15)
            )
            
            bonus_points = self._calculate_bonus_points()
            overall_score += bonus_points
            
            is_eligible = self._determine_eligibility(overall_score)
            
            self.evaluation_result.update({
                'is_eligible': is_eligible,
                'overall_score': round(overall_score, 2),
                'detailed_breakdown': {
                    'project_experience': {
                        'score': project_experience_score,
                        'weight': weights.get('project_experience', 0.25),
                        'weighted_score': project_experience_score * weights.get('project_experience', 0.25)
                    },
                    'skill_match': {
                        'score': skill_match_score,
                        'weight': weights.get('skill_match', 0.35),
                        'weighted_score': skill_match_score * weights.get('skill_match', 0.35)
                    },
                    'rating': {
                        'score': rating_score,
                        'weight': weights.get('rating', 0.25),
                        'weighted_score': rating_score * weights.get('rating', 0.25)
                    },
                    'deadline_compliance': {
                        'score': deadline_compliance_score,
                        'weight': weights.get('deadline_compliance', 0.15),
                        'weighted_score': deadline_compliance_score * weights.get('deadline_compliance', 0.15)
                    },
                    'obsp_experience': {
                        'score': obsp_experience_score,
                        'weight': 0,
                        'weighted_score': 0
                    },
                    'bonus_points': bonus_points
                }
            })
            
            return self.evaluation_result
            
        except Exception as e:
            self.evaluation_result.update({
                'error': str(e),
                'is_eligible': False
            })
            return self.evaluation_result
    
    def _evaluate_project_experience(self):
        """Evaluate project experience criteria"""
        try:
            required_domains = self.criteria.required_domains
            min_completed_projects = self.criteria.min_completed_projects
            min_project_budget = self.criteria.min_project_budget
            min_project_duration = self.criteria.min_project_duration_days
            
            completed_projects = Project.objects.filter(
                assigned_to=self.freelancer
            ).filter(
                status__in=['completed', 'Completed']
            )
            
            if required_domains:
                completed_projects = completed_projects.filter(
                    domain__name__in=required_domains
                )
            
            if min_project_budget > 0:
                completed_projects = completed_projects.filter(
                    budget__gte=min_project_budget
                )
            
            if min_project_duration > 0:
                projects_with_duration = []
                for project in completed_projects:
                    if project.created_at and project.deadline:
                        completion_date = project.deadline
                        duration = (completion_date - project.created_at.date()).days
                        if duration >= min_project_duration:
                            projects_with_duration.append(project.id)
                completed_projects = completed_projects.filter(id__in=projects_with_duration)
            
            actual_completed_projects = completed_projects.count()
            
            if actual_completed_projects >= min_completed_projects:
                score = 100
                self.evaluation_result['reasons'].append(
                    f"✅ Meets project experience requirement: {actual_completed_projects} completed projects"
                )
            else:
                score = (actual_completed_projects / min_completed_projects) * 100
                self.evaluation_result['reasons'].append(
                    f"❌ Insufficient project experience: {actual_completed_projects}/{min_completed_projects} required"
                )
            
            projects_data = list(completed_projects.values('id', 'title', 'budget', 'domain__name', 'created_at', 'deadline'))
            
            self.evaluation_result['proof']['project_experience'] = serialize_for_json({
                'completed_projects_count': actual_completed_projects,
                'required_projects': min_completed_projects,
                'required_domains': required_domains,
                'min_budget': float(min_project_budget),
                'min_duration_days': min_project_duration,
                'projects': projects_data
            })
            
            return round(score, 2)
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error evaluating project experience: {str(e)}")
            return 0
    
    def _evaluate_skill_match(self):
        """Evaluate skill match criteria including skills from completed projects"""
        try:
            required_skills = self.criteria.required_skills
            core_skills = self.criteria.core_skills
            optional_skills = self.criteria.optional_skills
            min_skill_match_percentage = self.criteria.min_skill_match_percentage
            
            profile_skills = set(self.freelancer_profile.skills.values_list('name', flat=True))
            
            completed_projects = Project.objects.filter(
                assigned_to=self.freelancer,
                status='completed'
            ).prefetch_related('skills_required')
            
            project_skills = set()
            for project in completed_projects:
                project_skill_names = project.skills_required.values_list('name', flat=True)
                project_skills.update(project_skill_names)
            
            freelancer_skills = profile_skills.union(project_skills)
            
            core_matches = freelancer_skills.intersection(set(core_skills))
            core_match_percentage = (len(core_matches) / len(core_skills)) * 100 if core_skills else 100
            
            required_matches = freelancer_skills.intersection(set(required_skills))
            required_match_percentage = (len(required_matches) / len(required_skills)) * 100 if required_skills else 100
            
            optional_matches = freelancer_skills.intersection(set(optional_skills))
            optional_bonus = len(optional_matches) * 5
            
            total_skill_match = required_match_percentage
            
            # Separate checks for better feedback
            skill_requirements_met = total_skill_match >= min_skill_match_percentage
            core_requirements_met = core_match_percentage >= 80

            if skill_requirements_met:
                self.evaluation_result['reasons'].append(
                    f"✅ Required skills match: {total_skill_match:.1f}% (minimum: {min_skill_match_percentage}%)"
                )
            else:
                missing_required = set(required_skills) - freelancer_skills
                self.evaluation_result['reasons'].append(
                    f"❌ Missing required skills: {', '.join(missing_required)}"
                )

            if core_requirements_met:
                self.evaluation_result['reasons'].append(
                    f"✅ Core skills match: {core_match_percentage:.1f}%"
                )
            else:
                missing_core = set(core_skills) - freelancer_skills
                self.evaluation_result['reasons'].append(
                    f"❌ Missing core skills: {', '.join(missing_core)}"
                )

            if optional_matches:
                self.evaluation_result['reasons'].append(
                    f"✅ Bonus skills: {', '.join(optional_matches)} (+{optional_bonus} points)"
                )
            
            score = total_skill_match
            if skill_requirements_met and core_requirements_met:
                score = min(100, total_skill_match + optional_bonus)

            self.evaluation_result['proof']['skill_match'] = {
                'required_skills': required_skills,
                'core_skills': core_skills,
                'optional_skills': optional_skills,
                'profile_skills': list(profile_skills),
                'project_skills': list(project_skills),
                'combined_skills': list(freelancer_skills),
                'required_matches': list(required_matches),
                'core_matches': list(core_matches),
                'optional_matches': list(optional_matches),
                'required_match_percentage': required_match_percentage,
                'core_match_percentage': core_match_percentage,
                'optional_bonus': optional_bonus,
                'min_required': min_skill_match_percentage,
                'projects_analyzed': list(completed_projects.values('id', 'title', 'skills_required__name'))
            }
            
            return round(score, 2)
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error evaluating skill match: {str(e)}")
            return 0
    
    def _evaluate_rating(self):
        """Evaluate rating criteria using Feedback model"""
        try:
            min_avg_rating = self.criteria.min_avg_rating
            
            feedback_ratings = Feedback.objects.filter(
                to_user=self.freelancer,
                is_reply=False
            ).values_list('rating', flat=True)
            
            review_ratings = FreelancerReview.objects.filter(
                to_freelancer=self.freelancer
            ).values_list('rating', flat=True)
            
            all_ratings = list(feedback_ratings) + list(review_ratings)
            
            if all_ratings:
                avg_rating = sum(all_ratings) / len(all_ratings)
                if avg_rating >= min_avg_rating:
                    score = min(100, (avg_rating / 5) * 100)
                    self.evaluation_result['reasons'].append(
                        f"✅ Meets rating requirement: {avg_rating:.2f} average rating"
                    )
                else:
                    score = (avg_rating / min_avg_rating) * 100
                    self.evaluation_result['reasons'].append(
                        f"❌ Insufficient rating: {avg_rating:.2f} (required: {min_avg_rating})"
                    )
            else:
                score = 0
                self.evaluation_result['reasons'].append("❌ No ratings available")
            
            self.evaluation_result['proof']['rating'] = {
                'average_rating': avg_rating if all_ratings else 0,
                'total_ratings': len(all_ratings),
                'feedback_ratings': list(feedback_ratings),
                'review_ratings': list(review_ratings),
                'min_required': min_avg_rating
            }
            
            return round(score, 2)
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error evaluating rating: {str(e)}")
            return 0
    
    def _evaluate_deadline_compliance(self):
        """Evaluate deadline compliance"""
        try:
            min_deadline_compliance = self.criteria.min_deadline_compliance
            
            completed_projects = Project.objects.filter(
                assigned_to=self.freelancer,
                status='completed'
            )
            
            if completed_projects.exists():
                on_time_projects = 0
                total_projects = completed_projects.count()
                
                for project in completed_projects:
                    if project.deadline:
                        on_time_projects += 1
                
                compliance_rate = (on_time_projects / total_projects) * 100
                
                if compliance_rate >= min_deadline_compliance:
                    score = min(100, compliance_rate)
                    self.evaluation_result['reasons'].append(
                        f"✅ Meets deadline compliance: {compliance_rate:.1f}%"
                    )
                else:
                    score = compliance_rate
                    self.evaluation_result['reasons'].append(
                        f"❌ Insufficient deadline compliance: {compliance_rate:.1f}% (required: {min_deadline_compliance}%)"
                    )
            else:
                score = 0
                self.evaluation_result['reasons'].append("❌ No completed projects for deadline evaluation")
            
            self.evaluation_result['proof']['deadline_compliance'] = {
                'compliance_rate': compliance_rate if completed_projects.exists() else 0,
                'on_time_projects': on_time_projects if completed_projects.exists() else 0,
                'total_projects': total_projects if completed_projects.exists() else 0,
                'min_required': min_deadline_compliance
            }
            
            return round(score, 2)
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error evaluating deadline compliance: {str(e)}")
            return 0
    
    def _evaluate_obsp_experience(self):
        """Evaluate OBSP experience for higher levels"""
        try:
            min_obsp_completed = self.criteria.min_obsp_completed
    
            if min_obsp_completed == 0:
                return 100
    
            previous_level = self._get_previous_level()
    
            from OBSP.models import OBSPAssignment
            completed_obsps = OBSPAssignment.objects.filter(
                assigned_freelancer=self.freelancer,
                obsp_response__template=self.obsp_template,
                obsp_response__selected_level=previous_level,
                status='completed'
            ).count()
    
            if completed_obsps >= min_obsp_completed:
                score = 100
                self.evaluation_result['reasons'].append(
                    f"✅ Meets OBSP experience: {completed_obsps} completed at {previous_level} level"
                )
            else:
                score = (completed_obsps / min_obsp_completed) * 100
                self.evaluation_result['reasons'].append(
                    f"❌ Insufficient OBSP experience: {completed_obsps}/{min_obsp_completed} required at {previous_level} level"
                )
    
            self.evaluation_result['proof']['obsp_experience'] = {
                'completed_obsps': completed_obsps,
                'required_obsps': min_obsp_completed,
                'previous_level': previous_level
            }
    
            return round(score, 2)
    
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error evaluating OBSP experience: {str(e)}")
            return 0
    def _calculate_bonus_points(self):
        """Calculate bonus points from various criteria"""
        try:
            bonus_points = 0
            bonus_criteria = self.criteria.bonus_criteria
            
            if bonus_criteria.get('certification_bonus', 0) > 0:
                cert_count = self.freelancer_profile.certifications.count()
                bonus_points += cert_count * bonus_criteria['certification_bonus']
            
            if bonus_criteria.get('portfolio_bonus', 0) > 0:
                portfolio_count = self.freelancer_profile.portfolio_items.count()
                bonus_points += portfolio_count * bonus_criteria['portfolio_bonus']
            
            if bonus_criteria.get('client_feedback_bonus', 0) > 0:
                feedback_count = Feedback.objects.filter(
                    to_user=self.freelancer,
                    is_reply=False
                ).count()
                bonus_points += feedback_count * bonus_criteria['client_feedback_bonus']
            
            if bonus_criteria.get('mobile_experience_bonus', 0) > 0:
                mobile_projects = Project.objects.filter(
                    assigned_to=self.freelancer,
                    domain__name='Mobile Development',
                    status='completed'
                ).count()
                bonus_points += mobile_projects * bonus_criteria['mobile_experience_bonus']
            
            if bonus_criteria.get('app_store_published_bonus', 0) > 0:
                app_store_projects = self.freelancer_profile.portfolio_items.filter(
                    project_url__icontains='appstore'
                ).count()
                bonus_points += app_store_projects * bonus_criteria['app_store_published_bonus']
            
            return round(bonus_points, 2)
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error calculating bonus points: {str(e)}")
            return 0
    
    def _determine_eligibility(self, overall_score):
        """Determine final eligibility based on overall score and criteria"""
        try:
            min_requirements_met = True
            
            project_proof = self.evaluation_result['proof'].get('project_experience', {})
            if project_proof.get('completed_projects_count', 0) < self.criteria.min_completed_projects:
                min_requirements_met = False
            
            skill_proof = self.evaluation_result['proof'].get('skill_match', {})
            if skill_proof.get('required_match_percentage', 0) < self.criteria.min_skill_match_percentage:
                min_requirements_met = False
            
            rating_proof = self.evaluation_result['proof'].get('rating', {})
            if rating_proof.get('average_rating', 0) < self.criteria.min_avg_rating:
                min_requirements_met = False
            
            if self.criteria.min_obsp_completed > 0:
                obsp_proof = self.evaluation_result['proof'].get('obsp_experience', {})
                if obsp_proof.get('completed_obsps', 0) < self.criteria.min_obsp_completed:
                    min_requirements_met = False
            
            is_eligible = min_requirements_met and overall_score >= 70
            
            return is_eligible
            
        except Exception as e:
            self.evaluation_result['reasons'].append(f"Error determining eligibility: {str(e)}")
            return False
    
    def _get_previous_level(self):
        """Get the previous level for OBSP experience requirement"""
        level_order = {'easy': 1, 'medium': 2, 'hard': 3}
        current_level_order = level_order.get(self.level, 1)
        
        if current_level_order == 1:
            return 'easy'
        elif current_level_order == 2:
            return 'easy'
        else:
            return 'medium'

class OBSPEligibilityCalculator:
    """
    Main calculator class that orchestrates eligibility evaluation
    """
    
    @staticmethod
    def calculate_eligibility(freelancer, obsp_template, level):
        import time
        start_time = time.time()
        
        try:
            evaluator = OBSPEligibilityEvaluator(freelancer, obsp_template, level)
            result = evaluator.evaluate_eligibility()
            
            end_time = time.time()
            duration = end_time - start_time
            
            return (
                result.get('is_eligible', False),
                result.get('overall_score', 0),
                result,
                duration
            )
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            return (
                False,
                0,
                {
                    'error': str(e),
                    'is_eligible': False,
                    'overall_score': 0
                },
                duration
            )
    
    @staticmethod
    def calculate_all_levels(freelancer, obsp_template):
        results = {}
        
        for level in ['easy', 'medium', 'hard']:
            try:
                is_eligible, score, analysis, duration = OBSPEligibilityCalculator.calculate_eligibility(
                    freelancer, obsp_template, level
                )
                
                results[level] = {
                    'is_eligible': is_eligible,
                    'score': score,
                    'analysis': analysis,
                    'duration': duration
                }
                
            except Exception as e:
                results[level] = {
                    'is_eligible': False,
                    'score': 0,
                    'analysis': {'error': str(e)},
                    'duration': 0
                }
        
        return results
