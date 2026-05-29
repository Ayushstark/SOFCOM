PRODUCT_PROMPTS = [
    "Build a CRM with login, contacts, dashboard, role-based access, premium plan with payments. Admins can see analytics.",
    "Create an ecommerce store with products, orders, customers, checkout payments, and admin analytics.",
    "Build an LMS for courses, lessons, students, enrollments, login, and progress dashboard.",
    "Make a clinic booking app with appointments, staff, services, reminders, and admin reports.",
    "Create a project management app with projects, tasks, teams, comments, and role permissions.",
    "Build a subscription SaaS dashboard with billing, user login, premium features, and admin metrics.",
    "Create a contact manager with companies, deals, tasks, search, and owner-only access.",
    "Build a store operations console with inventory, orders, customers, payments, and reports.",
    "Make a student course portal with login, courses, lessons, and dashboard analytics.",
    "Build an appointment scheduling product with customers, services, calendar dashboard, and payments.",
]

EDGE_CASE_PROMPTS = [
    "Build an app.",
    "Make something for my business with users and admin maybe payments or not?",
    "Create a CRM but no database and also save contacts forever.",
    "Build a dashboard with analytics but users should not login and admins should have private reports.",
    "I need a premium free paid app for everyone and only subscribers.",
    "Make a project tool with tasks, but no users, yet every task needs an owner.",
    "Create a booking system for clinics or schools?",
    "Build a store without products but include checkout.",
    "Need login, roles, dashboards, payments, analytics, contacts, orders, appointments, courses, everything.",
    "Make an app with admin analytics and role access.",
]

DATASET = [{"kind": "product", "prompt": prompt} for prompt in PRODUCT_PROMPTS] + [
    {"kind": "edge", "prompt": prompt} for prompt in EDGE_CASE_PROMPTS
]
