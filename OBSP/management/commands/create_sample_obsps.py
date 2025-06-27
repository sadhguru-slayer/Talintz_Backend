from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from OBSP.models import OBSPTemplate, OBSPLevel, OBSPField, OBSPMilestone
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Create sample OBSP templates for testing'

    def handle(self, *args, **options):
        # Get or create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@talintz.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        
        # Create Tech OBSP - AI-Powered E-commerce Platform
        self.create_tech_obsp(admin_user)
        
        # Create Creative OBSP - Brand Identity & Marketing Package
        self.create_creative_obsp(admin_user)
        
        self.stdout.write(self.style.SUCCESS('Successfully created sample OBSPs'))

    def create_tech_obsp(self, admin_user):
        """Create AI-Powered E-commerce Platform OBSP"""
        
        # Create OBSP Template
        tech_obsp = OBSPTemplate.objects.create(
            title="AI-Powered E-commerce Platform",
            category="web-development",
            industry="tech",
            description="Build a cutting-edge e-commerce platform powered by AI for personalized shopping experiences, intelligent recommendations, and automated inventory management.",
            base_price=50000,
            currency="INR",
            is_active=True,
            created_by=admin_user
        )
        
        # Create Levels
        basic_level = OBSPLevel.objects.create(
            template=tech_obsp,
            level="easy",
            name="Starter E-commerce",
            price=50000,
            duration="4-6 weeks",
            features=[
                "Responsive e-commerce website",
                "Product catalog with search",
                "Shopping cart & checkout",
                "Basic payment integration",
                "Admin dashboard",
                "Mobile-friendly design",
                "SEO optimization",
                "Basic analytics"
            ],
            deliverables=[
                "Fully functional e-commerce website",
                "Admin panel for product management",
                "Payment gateway integration",
                "Mobile responsive design",
                "SEO optimized pages",
                "Basic analytics setup",
                "User manual & documentation",
                "1 month support"
            ],
            order=1
        )
        
        pro_level = OBSPLevel.objects.create(
            template=tech_obsp,
            level="medium",
            name="AI-Enhanced E-commerce",
            price=120000,
            duration="8-10 weeks",
            features=[
                "All Starter features",
                "AI-powered product recommendations",
                "Personalized user experience",
                "Advanced search with filters",
                "Inventory management system",
                "Customer review system",
                "Email marketing integration",
                "Advanced analytics dashboard",
                "Multi-language support",
                "Advanced security features"
            ],
            deliverables=[
                "AI-powered e-commerce platform",
                "Advanced admin dashboard",
                "Recommendation engine",
                "Inventory management system",
                "Customer analytics",
                "Email marketing tools",
                "Multi-language support",
                "Security audit report",
                "Comprehensive documentation",
                "3 months support"
            ],
            order=2
        )
        
        enterprise_level = OBSPLevel.objects.create(
            template=tech_obsp,
            level="hard",
            name="Enterprise AI Commerce",
            price=250000,
            duration="12-16 weeks",
            features=[
                "All Pro features",
                "Advanced AI personalization",
                "Predictive inventory management",
                "Real-time analytics",
                "Multi-vendor marketplace",
                "Advanced fraud detection",
                "API integration capabilities",
                "Custom reporting tools",
                "White-label solution",
                "Enterprise security",
                "Scalable architecture",
                "24/7 monitoring"
            ],
            deliverables=[
                "Enterprise-grade e-commerce platform",
                "Advanced AI algorithms",
                "Multi-vendor marketplace",
                "Custom API development",
                "Advanced security implementation",
                "Performance optimization",
                "Scalability architecture",
                "Comprehensive testing",
                "Deployment & migration",
                "6 months support",
                "Training sessions"
            ],
            order=3
        )
        
        # Create Fields for Tech OBSP
        self.create_tech_fields(tech_obsp)
        
        # Create Milestones for Tech OBSP
        self.create_tech_milestones(tech_obsp, basic_level, pro_level, enterprise_level)
        
        self.stdout.write(self.style.SUCCESS(f'Created Tech OBSP: {tech_obsp.title}'))

    def create_creative_obsp(self, admin_user):
        """Create Brand Identity & Marketing Package OBSP"""
        
        # Create OBSP Template
        creative_obsp = OBSPTemplate.objects.create(
            title="Brand Identity & Marketing Package",
            category="design",
            industry="entertainment",
            description="Complete brand transformation package including logo design, visual identity, marketing materials, and digital presence to establish a strong brand in the market.",
            base_price=25000,
            currency="INR",
            is_active=True,
            created_by=admin_user
        )
        
        # Create Levels
        basic_creative = OBSPLevel.objects.create(
            template=creative_obsp,
            level="easy",
            name="Essential Branding",
            price=25000,
            duration="2-3 weeks",
            features=[
                "Logo design (3 concepts)",
                "Brand color palette",
                "Typography selection",
                "Business card design",
                "Letterhead design",
                "Basic social media templates",
                "Brand guidelines document",
                "Source files delivery"
            ],
            deliverables=[
                "Professional logo design",
                "Complete brand identity kit",
                "Print-ready business materials",
                "Social media templates",
                "Brand guidelines PDF",
                "All source files (AI, PSD)",
                "Usage guidelines",
                "2 revision rounds"
            ],
            order=1
        )
        
        pro_creative = OBSPLevel.objects.create(
            template=creative_obsp,
            level="medium",
            name="Complete Brand Package",
            price=75000,
            duration="4-5 weeks",
            features=[
                "All Essential features",
                "Extended logo variations",
                "Comprehensive brand identity",
                "Marketing collateral design",
                "Website mockups",
                "Social media strategy",
                "Content creation guidelines",
                "Brand voice development",
                "Competitor analysis",
                "Brand positioning strategy"
            ],
            deliverables=[
                "Complete brand identity system",
                "Marketing collateral package",
                "Website design mockups",
                "Social media strategy document",
                "Content creation guidelines",
                "Brand positioning report",
                "Competitor analysis",
                "All source files",
                "3 revision rounds",
                "Brand consultation sessions"
            ],
            order=2
        )
        
        enterprise_creative = OBSPLevel.objects.create(
            template=creative_obsp,
            level="hard",
            name="Full Brand Transformation",
            price=150000,
            duration="6-8 weeks",
            features=[
                "All Complete features",
                "Comprehensive brand audit",
                "Custom illustration set",
                "Motion graphics & animations",
                "Video content creation",
                "Print & digital campaigns",
                "Brand launch strategy",
                "Marketing automation setup",
                "Performance tracking",
                "Ongoing brand support",
                "Team training sessions"
            ],
            deliverables=[
                "Complete brand transformation",
                "Custom illustration library",
                "Motion graphics package",
                "Video content library",
                "Marketing campaign materials",
                "Brand launch strategy",
                "Marketing automation setup",
                "Performance tracking tools",
                "Team training materials",
                "6 months brand support",
                "All source files & assets"
            ],
            order=3
        )
        
        # Create Fields for Creative OBSP
        self.create_creative_fields(creative_obsp)
        
        # Create Milestones for Creative OBSP
        self.create_creative_milestones(creative_obsp, basic_creative, pro_creative, enterprise_creative)
        
        self.stdout.write(self.style.SUCCESS(f'Created Creative OBSP: {creative_obsp.title}'))

    def create_tech_fields(self, template):
        """Create fields for Tech OBSP"""
        
        # Phase 1: Basic Info
        OBSPField.objects.create(
            template=template,
            field_type="text",
            label="Company Name",
            placeholder="Enter your company name",
            help_text="The name of your business or organization",
            is_required=True,
            has_price_impact=False,
            order=1,
            phase="basic",
            visibility_rule="generic"
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="textarea",
            label="Business Description",
            placeholder="Describe your business, products, and target audience",
            help_text="Tell us about your business model and what you sell",
            is_required=True,
            has_price_impact=False,
            order=2,
            phase="basic",
            visibility_rule="generic"
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="number",
            label="Expected Monthly Orders",
            placeholder="e.g., 1000",
            help_text="Estimated number of orders you expect to process monthly",
            is_required=True,
            has_price_impact=True,
            price_impact=15000,
            order=3,
            phase="basic",
            visibility_rule="generic"
        )
        
        # Phase 2: Core Features
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="Payment Methods",
            help_text="Select payment methods you want to integrate",
            is_required=True,
            has_price_impact=True,
            price_impact=5000,
            order=4,
            phase="core_features",
            visibility_rule="generic",
            options=[
                {"text": "Credit/Debit Cards", "price": 5000, "description": "Secure card processing"},
                {"text": "UPI Payments", "price": 3000, "description": "Instant UPI transfers"},
                {"text": "Digital Wallets", "price": 4000, "description": "Paytm, PhonePe, etc."},
                {"text": "Bank Transfers", "price": 2000, "description": "Direct bank transfers"},
                {"text": "Buy Now Pay Later", "price": 8000, "description": "EMI options for customers"}
            ]
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="radio",
            label="Inventory Management",
            help_text="Choose your inventory management needs",
            is_required=True,
            has_price_impact=True,
            price_impact=10000,
            order=5,
            phase="core_features",
            visibility_rule="generic",
            options=[
                {"text": "Basic Inventory", "price": 0, "description": "Simple stock tracking"},
                {"text": "Advanced Inventory", "price": 10000, "description": "Real-time stock management"},
                {"text": "AI-Powered Inventory", "price": 25000, "description": "Predictive stock management"}
            ]
        )
        
        # Phase 3: Add-ons
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="AI Features",
            help_text="Select AI-powered features to enhance user experience",
            is_required=False,
            has_price_impact=True,
            price_impact=20000,
            order=6,
            phase="add_ons",
            visibility_rule="mid_high",
            options=[
                {"text": "Product Recommendations", "price": 20000, "description": "AI-powered suggestions"},
                {"text": "Chatbot Support", "price": 15000, "description": "24/7 customer support"},
                {"text": "Price Optimization", "price": 12000, "description": "Dynamic pricing algorithms"},
                {"text": "Fraud Detection", "price": 18000, "description": "Advanced security features"}
            ]
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="Advanced Analytics",
            help_text="Choose advanced analytics and reporting features",
            is_required=False,
            has_price_impact=True,
            price_impact=15000,
            order=7,
            phase="add_ons",
            visibility_rule="high",
            options=[
                {"text": "Real-time Analytics", "price": 15000, "description": "Live performance tracking"},
                {"text": "Custom Reports", "price": 10000, "description": "Tailored business insights"},
                {"text": "Predictive Analytics", "price": 20000, "description": "Future trend predictions"},
                {"text": "A/B Testing Tools", "price": 12000, "description": "Conversion optimization"}
            ]
        )
        
        # Phase 4: Review
        OBSPField.objects.create(
            template=template,
            field_type="radio",
            label="Support Level",
            help_text="Choose your preferred support package",
            is_required=True,
            has_price_impact=True,
            price_impact=5000,
            order=8,
            phase="review",
            visibility_rule="generic",
            options=[
                {"text": "Basic Support", "price": 0, "description": "Email support for 1 month"},
                {"text": "Priority Support", "price": 5000, "description": "Phone & email support for 3 months"},
                {"text": "Premium Support", "price": 15000, "description": "24/7 support for 6 months"}
            ]
        )

    def create_creative_fields(self, template):
        """Create fields for Creative OBSP"""
        
        # Phase 1: Basic Info
        OBSPField.objects.create(
            template=template,
            field_type="text",
            label="Brand Name",
            placeholder="Enter your brand or company name",
            help_text="The name that will represent your brand",
            is_required=True,
            has_price_impact=False,
            order=1,
            phase="basic",
            visibility_rule="generic"
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="textarea",
            label="Brand Story",
            placeholder="Tell us about your brand's story, mission, and values",
            help_text="Share your brand's journey and what makes it unique",
            is_required=True,
            has_price_impact=False,
            order=2,
            phase="basic",
            visibility_rule="generic"
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="select",
            label="Industry",
            help_text="Select your primary industry",
            is_required=True,
            has_price_impact=False,
            order=3,
            phase="basic",
            visibility_rule="generic",
            options=[
                {"text": "Technology", "price": 0, "description": "Tech startups and companies"},
                {"text": "Healthcare", "price": 0, "description": "Medical and wellness brands"},
                {"text": "Food & Beverage", "price": 0, "description": "Restaurants and food brands"},
                {"text": "Fashion", "price": 0, "description": "Clothing and fashion brands"},
                {"text": "Education", "price": 0, "description": "Educational institutions and courses"},
                {"text": "Finance", "price": 0, "description": "Financial services and fintech"},
                {"text": "Entertainment", "price": 0, "description": "Media and entertainment"},
                {"text": "Other", "price": 0, "description": "Other industries"}
            ]
        )
        
        # Phase 2: Core Features
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="Logo Design Style",
            help_text="Select your preferred logo design styles",
            is_required=True,
            has_price_impact=True,
            price_impact=5000,
            order=4,
            phase="core_features",
            visibility_rule="generic",
            options=[
                {"text": "Minimalist", "price": 0, "description": "Clean and simple design"},
                {"text": "Modern", "price": 2000, "description": "Contemporary and trendy"},
                {"text": "Vintage", "price": 3000, "description": "Classic and timeless"},
                {"text": "Playful", "price": 2500, "description": "Fun and energetic"},
                {"text": "Professional", "price": 1500, "description": "Corporate and formal"},
                {"text": "Creative", "price": 4000, "description": "Unique and artistic"}
            ]
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="radio",
            label="Brand Colors",
            help_text="Choose your brand color preference",
            is_required=True,
            has_price_impact=True,
            price_impact=3000,
            order=5,
            phase="core_features",
            visibility_rule="generic",
            options=[
                {"text": "Monochrome", "price": 0, "description": "Black, white, and grays"},
                {"text": "Bold Colors", "price": 2000, "description": "Vibrant and eye-catching"},
                {"text": "Pastel Colors", "price": 1500, "description": "Soft and gentle"},
                {"text": "Custom Palette", "price": 3000, "description": "Tailored color scheme"}
            ]
        )
        
        # Phase 3: Add-ons
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="Marketing Materials",
            help_text="Select additional marketing materials you need",
            is_required=False,
            has_price_impact=True,
            price_impact=10000,
            order=6,
            phase="add_ons",
            visibility_rule="mid_high",
            options=[
                {"text": "Social Media Templates", "price": 8000, "description": "Instagram, Facebook, LinkedIn"},
                {"text": "Email Marketing Templates", "price": 6000, "description": "Newsletter and campaign designs"},
                {"text": "Print Materials", "price": 12000, "description": "Brochures, flyers, posters"},
                {"text": "Video Content", "price": 25000, "description": "Promotional videos and animations"},
                {"text": "Website Design", "price": 30000, "description": "Complete website mockups"}
            ]
        )
        
        OBSPField.objects.create(
            template=template,
            field_type="checkbox",
            label="Brand Strategy",
            help_text="Choose additional brand strategy services",
            is_required=False,
            has_price_impact=True,
            price_impact=15000,
            order=7,
            phase="add_ons",
            visibility_rule="high",
            options=[
                {"text": "Brand Positioning", "price": 15000, "description": "Market positioning strategy"},
                {"text": "Competitor Analysis", "price": 10000, "description": "Detailed competitor research"},
                {"text": "Brand Voice Development", "price": 8000, "description": "Tone and messaging guidelines"},
                {"text": "Launch Strategy", "price": 20000, "description": "Complete brand launch plan"}
            ]
        )
        
        # Phase 4: Review
        OBSPField.objects.create(
            template=template,
            field_type="radio",
            label="Revision Rounds",
            help_text="Choose the number of revision rounds included",
            is_required=True,
            has_price_impact=True,
            price_impact=5000,
            order=8,
            phase="review",
            visibility_rule="generic",
            options=[
                {"text": "2 Revisions", "price": 0, "description": "Standard revision package"},
                {"text": "5 Revisions", "price": 5000, "description": "Extended revision package"},
                {"text": "Unlimited Revisions", "price": 15000, "description": "Premium revision package"}
            ]
        )

    def create_tech_milestones(self, template, basic_level, pro_level, enterprise_level):
        """Create milestones for Tech OBSP"""
        
        # Basic Level Milestones
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="requirement_review",
            title="Requirements Analysis & Planning",
            description="Detailed analysis of your business requirements, technical specifications, and project planning.",
            estimated_days=5,
            payout_percentage=20.00,
            deliverables=[
                "Detailed requirements document",
                "Technical specification",
                "Project timeline",
                "Resource allocation plan"
            ],
            quality_checklist=[
                "All business requirements documented",
                "Technical feasibility confirmed",
                "Timeline approved by client",
                "Resource requirements finalized"
            ],
            client_approval_required=True,
            order=1
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="design_approval",
            title="UI/UX Design & Prototype",
            description="Complete user interface design, user experience flow, and interactive prototype development.",
            estimated_days=10,
            payout_percentage=30.00,
            deliverables=[
                "Complete UI design mockups",
                "User experience flow diagrams",
                "Interactive prototype",
                "Design system documentation"
            ],
            quality_checklist=[
                "All pages designed and approved",
                "User flow optimized",
                "Mobile responsiveness confirmed",
                "Design consistency maintained"
            ],
            client_approval_required=True,
            order=2
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="development_progress",
            title="Core Development",
            description="Development of core e-commerce functionality including product management, cart, and checkout.",
            estimated_days=15,
            payout_percentage=40.00,
            deliverables=[
                "Core e-commerce functionality",
                "Product management system",
                "Shopping cart implementation",
                "Basic payment integration"
            ],
            quality_checklist=[
                "All core features functional",
                "Database structure optimized",
                "Security measures implemented",
                "Performance benchmarks met"
            ],
            client_approval_required=False,
            order=3
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="final_delivery",
            title="Testing & Launch",
            description="Comprehensive testing, bug fixes, and final deployment to production environment.",
            estimated_days=10,
            payout_percentage=10.00,
            deliverables=[
                "Fully tested e-commerce platform",
                "Production deployment",
                "User training materials",
                "Launch support"
            ],
            quality_checklist=[
                "All functionality tested",
                "Performance optimized",
                "Security audit completed",
                "Launch successful"
            ],
            client_approval_required=True,
            order=4
        )
        
        # Pro Level Milestones (additional milestones)
        OBSPMilestone.objects.create(
            template=template,
            level=pro_level,
            milestone_type="development_progress",
            title="AI Integration",
            description="Integration of AI-powered features including recommendation engine and personalization.",
            estimated_days=20,
            payout_percentage=25.00,
            deliverables=[
                "AI recommendation engine",
                "Personalization algorithms",
                "Advanced search functionality",
                "Analytics dashboard"
            ],
            quality_checklist=[
                "AI algorithms tested and optimized",
                "Recommendation accuracy verified",
                "Performance impact assessed",
                "User experience enhanced"
            ],
            client_approval_required=True,
            order=5
        )
        
        # Enterprise Level Milestones
        OBSPMilestone.objects.create(
            template=template,
            level=enterprise_level,
            milestone_type="development_progress",
            title="Enterprise Features",
            description="Development of enterprise-grade features including multi-vendor marketplace and advanced security.",
            estimated_days=25,
            payout_percentage=30.00,
            deliverables=[
                "Multi-vendor marketplace",
                "Advanced security features",
                "Enterprise API development",
                "Scalability implementation"
            ],
            quality_checklist=[
                "Enterprise features functional",
                "Security audit passed",
                "API documentation complete",
                "Scalability tested"
            ],
            client_approval_required=True,
            order=6
        )

    def create_creative_milestones(self, template, basic_level, pro_level, enterprise_level):
        """Create milestones for Creative OBSP"""
        
        # Basic Level Milestones
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="requirement_review",
            title="Brand Discovery & Research",
            description="In-depth brand research, competitor analysis, and discovery of your brand's unique positioning.",
            estimated_days=3,
            payout_percentage=20.00,
            deliverables=[
                "Brand research report",
                "Competitor analysis",
                "Brand positioning statement",
                "Design brief"
            ],
            quality_checklist=[
                "Brand research completed",
                "Competitors identified and analyzed",
                "Positioning strategy defined",
                "Design brief approved"
            ],
            client_approval_required=True,
            order=1
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="design_approval",
            title="Logo Design Concepts",
            description="Creation of multiple logo concepts with different styles and approaches for your brand.",
            estimated_days=7,
            payout_percentage=40.00,
            deliverables=[
                "3 logo design concepts",
                "Logo variations (horizontal, vertical, icon)",
                "Color palette options",
                "Typography recommendations"
            ],
            quality_checklist=[
                "3 distinct logo concepts created",
                "All logo variations provided",
                "Color palette finalized",
                "Typography selected"
            ],
            client_approval_required=True,
            order=2
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="development_progress",
            title="Brand Identity Development",
            description="Development of complete brand identity including business cards, letterhead, and basic materials.",
            estimated_days=5,
            payout_percentage=30.00,
            deliverables=[
                "Business card designs",
                "Letterhead design",
                "Basic social media templates",
                "Brand guidelines document"
            ],
            quality_checklist=[
                "All print materials designed",
                "Social media templates created",
                "Brand guidelines documented",
                "Files prepared for print"
            ],
            client_approval_required=True,
            order=3
        )
        
        OBSPMilestone.objects.create(
            template=template,
            level=basic_level,
            milestone_type="final_delivery",
            title="Final Delivery & Support",
            description="Final file preparation, source file delivery, and initial support period.",
            estimated_days=2,
            payout_percentage=10.00,
            deliverables=[
                "All source files (AI, PSD)",
                "Print-ready files",
                "Usage guidelines",
                "Brand guidelines PDF"
            ],
            quality_checklist=[
                "All files properly organized",
                "Print files prepared",
                "Guidelines comprehensive",
                "Client training completed"
            ],
            client_approval_required=True,
            order=4
        )
        
        # Pro Level Milestones
        OBSPMilestone.objects.create(
            template=template,
            level=pro_level,
            milestone_type="development_progress",
            title="Marketing Collateral",
            description="Development of comprehensive marketing materials and digital assets.",
            estimated_days=10,
            payout_percentage=25.00,
            deliverables=[
                "Marketing collateral package",
                "Website design mockups",
                "Social media strategy",
                "Content guidelines"
            ],
            quality_checklist=[
                "All marketing materials created",
                "Website mockups approved",
                "Strategy documented",
                "Guidelines comprehensive"
            ],
            client_approval_required=True,
            order=5
        )
        
        # Enterprise Level Milestones
        OBSPMilestone.objects.create(
            template=template,
            level=enterprise_level,
            milestone_type="development_progress",
            title="Advanced Creative Assets",
            description="Creation of advanced creative assets including motion graphics and video content.",
            estimated_days=15,
            payout_percentage=30.00,
            deliverables=[
                "Motion graphics package",
                "Video content library",
                "Custom illustrations",
                "Marketing campaigns"
            ],
            quality_checklist=[
                "Motion graphics completed",
                "Video content produced",
                "Illustrations created",
                "Campaigns developed"
            ],
            client_approval_required=True,
            order=6
        ) 