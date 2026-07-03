import os
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session
from app.models import User, Transaction, SavingsGoal, Badge, UserChallenge, Challenge

def generate_monthly_pdf(db: Session, user_id: int, year: int, month: int, output_path: str) -> str:
    """
    Generates a beautifully structured PDF financial report for a user for a given month.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
        
    start_date = datetime.date(year, month, 1)
    # Get last day of month
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    end_date = datetime.date(year, month, days_in_month)
    
    # Fetch data
    txs = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.date >= start_date,
        Transaction.date <= end_date
    ).all()
    
    active_goals = db.query(SavingsGoal).filter(
        SavingsGoal.user_id == user_id,
        SavingsGoal.status == "active"
    ).all()
    
    badges_earned = db.query(Badge).filter(
        Badge.user_id == user_id,
        Badge.earned_at >= datetime.datetime(year, month, 1),
        Badge.earned_at <= datetime.datetime(year, month, days_in_month, 23, 59, 59)
    ).all()
    
    completed_challenges = db.query(UserChallenge).filter(
        UserChallenge.user_id == user_id,
        UserChallenge.status == "completed",
        UserChallenge.end_date >= start_date,
        UserChallenge.end_date <= end_date
    ).all()
    
    # AI recommendations saved in DB
    from app.models import AIRecommendation
    recs= db.query(AIRecommendation).filter(AIRecommendation.user_id == user_id).all()
    
    # Calculate financial metrics
    total_income = sum(t.amount for t in txs if t.type == "income")
    total_expense = sum(t.amount for t in txs if t.type == "expense")
    
    # Add base monthly income if no income recorded
    if total_income == 0:
        total_income = user.monthly_income
        
    savings = total_income - total_expense
    savings = max(0.0, savings)
    
    utilization_rate = (total_expense / total_income * 100) if total_income > 0 else 0.0
    
    # Group expenses by category
    category_map = {}
    for t in txs:
        if t.type == "expense":
            category_map[t.category] = category_map.get(t.category, 0.0) + t.amount
            
    # Setup document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=55, bottomMargin=55
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette - Rich Deep Blue & Mint Green theme
    primary_color = colors.HexColor("#1A365D")   # Deep Blue
    secondary_color = colors.HexColor("#2C3E50") # Navy Gray
    accent_color = colors.HexColor("#0D9488")    # Teal/Mint
    bg_light = colors.HexColor("#F8FAFC")        # Soft Slate Grey
    text_dark = colors.HexColor("#1E293B")       # Dark Charcoal
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=primary_color,
        spaceAfter=15,
        alignment=TA_LEFT
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        textColor=colors.HexColor("#475569"),
        spaceAfter=25,
        alignment=TA_LEFT
    )
    
    h1_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=10,
        alignment=TA_LEFT
    )
    
    body_style = ParagraphStyle(
        'BodyTextDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=text_dark,
        leading=14
    )
    
    card_label_style = ParagraphStyle(
        'CardLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER
    )
    
    card_value_style = ParagraphStyle(
        'CardValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=primary_color,
        alignment=TA_CENTER
    )
    
    recommendation_style = ParagraphStyle(
        'Recommendation',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        textColor=colors.HexColor("#0369A1"), # Dark sky blue
        leading=14
    )
    
    story = []
    
    # Header Section
    month_name = calendar.month_name[month]
    story.append(Paragraph(f"SafeMoney Monthly Report", title_style))
    story.append(Paragraph(f"Financial summary and performance review for <b>{month_name} {year}</b>", subtitle_style))
    story.append(Spacer(1, 10))
    
    # Key Performance Cards (2x2 Grid)
    metrics_data = [
        [
            Paragraph("Total Monthly Income", card_label_style),
            Paragraph("Total Monthly Expenses", card_label_style),
            Paragraph("Monthly Savings Achieved", card_label_style),
            Paragraph("Financial Health Score", card_label_style)
        ],
        [
            Paragraph(f"₹{total_income:,.2f}", card_value_style),
            Paragraph(f"₹{total_expense:,.2f}", card_value_style),
            Paragraph(f"₹{savings:,.2f}", card_value_style),
            Paragraph(f"{user.financial_health_score}/100", card_value_style)
        ]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[130, 130, 130, 130])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#64748B")),
        ('PADDING', (0,0), (-1,-1), 12),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 20))
    
    # Category Expenditure Breakdown
    story.append(Paragraph("Category Spending Breakdown", h1_style))
    
    category_rows = [["Category", "Amount Spent (₹)", "Percentage (%)"]]
    sorted_categories = sorted(category_map.items(), key=lambda x: x[1], reverse=True)
    for cat, amt in sorted_categories:
        pct = (amt / total_expense * 100) if total_expense > 0 else 0.0
        category_rows.append([
            Paragraph(f"<b>{cat}</b>", body_style),
            f"₹{amt:,.2f}",
            f"{pct:.1f}%"
        ])
    
    # If no categories, add a placeholder
    if len(sorted_categories) == 0:
        category_rows.append(["No expense data", "₹0.00", "0.0%"])
        
    category_table = Table(category_rows, colWidths=[200, 160, 160])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    
    # Set header cell text colors
    for col in range(3):
        category_table.setStyle(TableStyle([
            ('TEXTCOLOR', (col,0), (col,0), colors.white),
            ('FONTNAME', (col,0), (col,0), 'Helvetica-Bold')
        ]))
    story.append(category_table)
    story.append(Spacer(1, 20))
    
    # Active Savings Goals
    story.append(Paragraph("Active Savings Goals Status", h1_style))
    goals_rows = [["Goal Title", "Target Amount", "Current Savings", "Monthly Contribution", "Progress"]]
    for goal in active_goals:
        progress_pct = (goal.current_amount / goal.target_amount * 100) if goal.target_amount > 0 else 0.0
        goals_rows.append([
            Paragraph(f"<b>{goal.title}</b> ({goal.purpose})", body_style),
            f"₹{goal.target_amount:,.2f}",
            f"₹{goal.current_amount:,.2f}",
            f"₹{goal.monthly_contribution:,.2f}/mo",
            f"{progress_pct:.1f}%"
        ])
        
    if len(active_goals) == 0:
        goals_rows.append(["No active savings goals found", "-", "-", "-", "-"])
        
    goals_table = Table(goals_rows, colWidths=[160, 90, 90, 110, 70])
    goals_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), secondary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    for col in range(5):
        goals_table.setStyle(TableStyle([
            ('TEXTCOLOR', (col,0), (col,0), colors.white),
            ('FONTNAME', (col,0), (col,0), 'Helvetica-Bold')
        ]))
    story.append(goals_table)
    story.append(Spacer(1, 20))
    
    # Detailed Transaction History List
    story.append(Paragraph("Detailed Transaction History", h1_style))
    
    tx_headers = ["Date / Time", "Description", "Type / Category", "Method", "Amount", "Balance After"]
    tx_rows = [tx_headers]
    
    # Sort transactions chronologically (oldest first)
    sorted_txs = sorted(txs, key=lambda x: (x.date, x.time))
    
    for t in sorted_txs:
        # Date & Time formatting
        t_time_str = t.time.strftime('%H:%M') if isinstance(t.time, datetime.time) else str(t.time)[:5]
        dt_str = f"{t.date}\n{t_time_str}"
        
        # Description formatting (including Sender and Notes if present)
        desc_text = f"<b>{t.description}</b>"
        if getattr(t, "sender", None):
            desc_text += f"<br/><font color='#0D9488' size='8'>From: {t.sender}</font>"
        if t.notes:
            desc_text += f"<br/><font color='#64748B' size='8'><i>{t.notes}</i></font>"
            
        # Category/Type formatting
        cat_text = t.income_type if (t.type == "income" and getattr(t, "income_type", None)) else t.category
        
        # Amount formatting
        amt_sign = "+" if t.type == "income" else "-"
        amt_color = "#10B981" if t.type == "income" else "#EF4444"
        amt_text = f"<font color='{amt_color}'><b>{amt_sign} ₹{t.amount:,.2f}</b></font>"
        
        # Balance After formatting
        balance_after_val = f"₹{t.updated_balance:,.2f}" if (getattr(t, "updated_balance", None) is not None) else "—"
        
        tx_rows.append([
            Paragraph(dt_str.replace('\n', '<br/>'), body_style),
            Paragraph(desc_text, body_style),
            Paragraph(cat_text, body_style),
            Paragraph(t.payment_method, body_style),
            Paragraph(amt_text, body_style),
            Paragraph(balance_after_val, body_style)
        ])
        
    if len(txs) == 0:
        tx_rows.append(["No transactions recorded for this period", "", "", "", "", ""])
        
    tx_table = Table(tx_rows, colWidths=[75, 140, 95, 65, 77, 80], repeatRows=1)
    tx_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
    ]))
    for col in range(6):
        tx_table.setStyle(TableStyle([
            ('TEXTCOLOR', (col,0), (col,0), colors.white),
            ('FONTNAME', (col,0), (col,0), 'Helvetica-Bold')
        ]))
    
    story.append(tx_table)
    story.append(Spacer(1, 20))
    
    # Gamification: Challenges & Badges
    story.append(Paragraph("Gamification & Achievements", h1_style))
    gamification_details = []
    
    badge_list_str = ", ".join([b.name for b in badges_earned]) if badges_earned else "None"
    gamification_details.append(Paragraph(f"<b>Badges Earned This Month:</b> {badge_list_str}", body_style))
    
    challenges_completed_count = len(completed_challenges)
    gamification_details.append(Paragraph(f"<b>Monthly Challenges Completed:</b> {challenges_completed_count}", body_style))
    
    gamification_details.append(Paragraph(f"<b>Current Loyalty & Discipline Points:</b> {user.points} XP", body_style))
    
    for item in gamification_details:
        story.append(item)
        story.append(Spacer(1, 6))
    
    story.append(Spacer(1, 15))
    
    # AI-Powered Financial Recommendations
    story.append(Paragraph("AI-Powered Budget Optimization Recommendations", h1_style))
    
    recs_container = []
    if recs:
        for r in recs:
            recs_container.append(Paragraph(f"• {r.suggestion}", recommendation_style))
            recs_container.append(Spacer(1, 4))
    else:
        recs_container.append(Paragraph("• Continue tracking transactions daily to unlock custom budgeting strategies and AI insights.", recommendation_style))
        
    recs_table = Table([[recs_container]], colWidths=[520])
    recs_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")), # Light blue warning/info bg
        ('PADDING', (0,0), (-1,-1), 12),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#BAE6FD")),
    ]))
    story.append(recs_table)
    
    # Build Document
    doc.build(story, onFirstPage=add_first_page_footer, onLaterPages=add_later_page_header_footer)
    return output_path

def add_first_page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(40, 45, 572, 45)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    canvas.drawString(40, 32, f"Generated on: {now_str}")
    canvas.drawRightString(572, 32, f"Page {doc.page}")
    canvas.restoreState()

def add_later_page_header_footer(canvas, doc):
    canvas.saveState()
    # Draw header
    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(40, 755, "SafeMoney – Personal Finance Management Report")
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(40, 747, 572, 747)
    
    # Draw footer
    canvas.line(40, 45, 572, 45)
    canvas.setFont('Helvetica', 8)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    canvas.drawString(40, 32, f"Generated on: {now_str}")
    canvas.drawRightString(572, 32, f"Page {doc.page}")
    canvas.restoreState()
