from flask import Flask, render_template, request, jsonify, session
from datetime import datetime, timedelta
import json
import os
import re
from typing import Dict, List, Optional, Union

app = Flask(__name__)

# Simple in-memory storage for demo purposes
# In a production environment, use a proper database
conversations = {}

# Emergency resources
EMERGENCY_RESOURCES = {
    'crisis': 'Telefonseelsorge: 0800 111 0 111 (kostenlos, 24/7 erreichbar)',
    'debt_advice': 'Schuldnerberatung: www.schuldnerberatung.de',
    'mental_health': 'Psychologische Beratung: 116 123 (kostenlos, rund um die Uhr)'
}

# Expense categories with examples
EXPENSE_CATEGORIES = {
    'Wohnen': ['Miete', 'Nebenkosten', 'Strom', 'Gas', 'Wasser', 'Hausratversicherung'],
    'Lebensmittel': ['Supermarkt', 'Getränke', 'Haushaltsartikel'],
    'Mobilität': ['ÖPNV', 'Auto', 'Fahrrad', 'Tanken', 'Versicherung', 'Steuern'],
    'Gesundheit': ['Krankenkasse', 'Zuzahlungen', 'Medikamente', 'Therapien'],
    'Versicherungen': ['Haftpflicht', 'Rechtsschutz', 'Berufsunfähigkeit'],
    'Freizeit': ['Hobbys', 'Sport', 'Abos', 'Streaming', 'Ausgehen']
}

# Initial greeting
GREETING = "Hallo! Ich bin SchuldenKompass. Erzähl mir: Was beschäftigt dich gerade am meisten, wenn du an deine finanzielle Situation denkst?"

# Define the conversation flow
CONVERSATION_FLOW = [
    {
        'key': 'main_concern',
        'question': 'Das klingt wirklich belastend. Vielen Dank, dass du das mit mir teilst. Um dir konkret helfen zu können, wäre es gut zu wissen: Wie hoch ist dein aktuelles monatliches Einkommen?',
        'type': 'number',
        'hint': 'Dein Nettoeinkommen in Euro (z.B. 1450)',
        'validation': 'positive_number',
        'error': 'Ich konnte die Zahl nicht richtig verstehen. Bitte gib sie als ganze Euro-Zahl ein, zum Beispiel 1450.'
    },
    {
        'question': 'Danke für deine Angabe. Die Miete ist oft einer der größten Ausgaben. Um deine finanzielle Situation besser zu verstehen: Wie viel zahlst du monatlich für Miete inklusive Nebenkosten?',
        'key': 'rent',
        'type': 'number',
        'hint': 'Monatliche Miete in Euro (z.B. 650)',
        'validation': r'^\d+([.,]\d{1,2})?$',
        'error': 'Ich konnte die Miete nicht richtig verstehen. Bitte gib den Betrag als Zahl ein, zum Beispiel 650 oder 650,00.'
    },
    {
        'key': 'expenses',
        'question': 'Danke für deine Angabe. Lass uns jetzt deine anderen regelmäßigen Ausgaben anschauen. Was gibst du monatlich für Versicherungen, Handy, Abos und ähnliches aus?',
        'type': 'number',
        'hint': 'Monatliche Ausgaben in Euro (z.B. 300)',
        'validation': 'positive_number',
        'error': 'Ich konnte die Zahl nicht richtig verstehen. Bitte gib den Betrag als Zahl ein, zum Beispiel 300.'
    },
    {
        'question': 'Ich verstehe, dass das nicht einfach ist, darüber zu sprechen. Um dir bestmöglich zu helfen: Wie hoch schätzt du deine gesamten Schulden ein? Das hilft mir, die Situation besser zu verstehen.',
        'key': 'total_debt',
        'type': 'number',
        'hint': 'Gesamtsumme in Euro',
        'validation': r'^\d+([.,]\d{1,2})?$',
        'error': 'Könntest du mir bitte eine ungefähre Summe nennen? Das hilft mir, dir besser zu helfen.'
    },
    {
        'question': 'Danke für deine Offenheit. Bei wie vielen verschiedenen Stellen hast du Schulden? Das können Banken, Händler oder andere Gläubiger sein.',
        'key': 'creditors_count',
        'type': 'number',
        'hint': 'Anzahl der Gläubiger',
        'validation': r'^\d+$',
        'error': 'Es wäre hilfreich zu wissen, bei wie vielen Stellen du Schulden hast. Kannst du das kurz schätzen?'
    },
    {
        'question': 'Ich verstehe, dass das unangenehm sein kann, aber es ist wichtig, dass wir die Dringlichkeit einschätzen können: Sind bereits Mahnungen oder Zahlungserinnerungen bei dir eingegangen?',
        'key': 'has_warnings',
        'type': 'choice',
        'options': ['Ja', 'Noch nicht', 'Ich bin mir nicht sicher'],
        'hint': 'Antworte mit Ja/Nein/Weiß nicht'
    },
    {
        'question': 'Drohen dir bereits rechtliche Konsequenzen wie Kontopfändung, Lohnpfändung oder Kündigung der Wohnung?',
        'key': 'legal_issues',
        'type': 'choice',
        'options': ['Ja', 'Nein', 'Weiß nicht'],
        'hint': 'Antworte mit Ja/Nein/Weiß nicht'
    }
]

def extract_number(text: str) -> Optional[float]:
    """Extract number from text, handling different decimal separators."""
    # Remove all non-digit characters except commas and dots
    clean_text = re.sub(r'[^\d,.]', '', text)
    if not clean_text:
        return None
    
    # Handle different decimal separators
    if ',' in clean_text and '.' in clean_text:
        # If both separators exist, the last one is the decimal point
        if clean_text.rfind(',') > clean_text.rfind('.'):
            clean_text = clean_text.replace('.', '').replace(',', '.')
        else:
            clean_text = clean_text.replace(',', '')
    elif ',' in clean_text:
        # Comma as decimal separator
        clean_text = clean_text.replace('.', '').replace(',', '.')
    
    try:
        return float(clean_text)
    except (ValueError, TypeError):
        return None

def format_currency(amount: float) -> str:
    """Format number as currency string."""
    return f"{amount:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')

def get_next_question(conversation_state: dict) -> str:
    """Get the next question based on conversation state."""
    if 'step' not in conversation_state:
        return GREETING
    
    current_step = conversation_state.get('step', 0)
    
    # If we've completed the main flow, handle the next steps
    if current_step >= len(CONVERSATION_FLOW):
        return None
    
    question_data = CONVERSATION_FLOW[current_step]
    question = question_data['question']
    
    # Add hint if available
    if 'hint' in question_data:
        question += f"\n\n({question_data['hint']})"
    
    return question

def validate_input(user_input: str, field_type: str, validation: str = None, options: list = None) -> tuple:
    """Validate user input based on field type and validation rules."""
    user_input = user_input.strip()
    
    if field_type == 'number':
        number = extract_number(user_input)
        if number is None:
            return False, "Bitte gib eine gültige Zahl ein."
        if validation == 'positive_number':
            if number <= 0:
                return False, "Bitte gib eine positive Zahl ein."
            return True, number
        elif validation and not re.match(validation, user_input):
            return False, "Ungültiges Format. Bitte versuche es noch einmal."
        return True, number
    
    elif field_type == 'choice':
        if not options:
            return True, user_input
            
        # Try to match user input with available options
        user_input_lower = user_input.lower()
        matched_options = [opt for opt in options if opt.lower().startswith(user_input_lower)]
        
        if len(matched_options) == 1:
            return True, matched_options[0]
        elif len(matched_options) > 1:
            return False, f"Meintest du eine dieser Optionen? {', '.join(matched_options)}"
        else:
            return False, f"Bitte wähle eine der Optionen: {', '.join(options)}"
    
    return True, user_input

def generate_financial_summary(data: dict) -> str:
    """Generate a summary of the user's financial situation."""
    # Try to convert string numbers to floats for calculations
    try:
        income = float(data.get('income', 0)) if isinstance(data.get('income'), (int, float)) else 0
        rent = float(data.get('rent', 0)) if isinstance(data.get('rent'), (int, float)) else 0
        expenses = float(data.get('expenses', 0)) if isinstance(data.get('expenses'), (int, float)) else 0
        total_debt = float(data.get('total_debt', 0)) if isinstance(data.get('total_debt'), (int, float)) else 0
        
        total_expenses = rent + expenses
        monthly_surplus = income - total_expenses
        
        # Calculate debt-free timeline (simplified)
        debt_free_months = None
        if monthly_surplus > 0 and total_debt > 0:
            debt_free_months = int((total_debt / monthly_surplus) + 0.5)  # Round to nearest month
        
        summary = [
            "🔍 *Deine finanzielle Situation im Überblick:*",
            "",
            f"💶 **Monatliches Einkommen:** {format_currency(income) if income > 0 else 'Nicht angegeben'}",
            f"🏠 **Wohnkosten (Miete & NK):** {format_currency(rent) if rent > 0 else 'Nicht angegeben'}",
            f"💳 **Sonstige Fixkosten:** {format_currency(expenses) if expenses > 0 else 'Nicht angegeben'}",
            ""
        ]
        
        if income > 0 and total_expenses > 0:
            summary.extend([
                f"📊 **Monatliche Ausgaben gesamt:** {format_currency(total_expenses)}",
                f"💰 **Verfügbarer Betrag pro Monat:** {format_currency(monthly_surplus)}",
                ""
            ])
        
        if total_debt > 0:
            summary.append(f"💸 **Geschätzte Gesamtschulden:** {format_currency(total_debt)}")
            
            if monthly_surplus > 0 and debt_free_months:
                debt_free_years = debt_free_months // 12
                debt_free_months_remainder = debt_free_months % 12
                timeline = f"{debt_free_years} Jahr{'e' if debt_free_years != 1 else ''} und {debt_free_months_remainder} Monat{'e' if debt_free_months_remainder != 1 else ''}"
                summary.append(f"📅 **Schuldenfrei in ca.:** {timeline} (bei gleichbleibender Sparrate)")
            
            summary.append("")
        
        # Add warning if expenses exceed income
        if income > 0 and total_expenses > income:
            monthly_deficit = total_expenses - income
            summary.extend([
                "⚠️ **Achtung:** Deine monatlichen Ausgaben übersteigen dein Einkommen um " + 
                f"{format_currency(monthly_deficit)} pro Monat.",
                ""
            ])
        
        # Add emergency resources if needed
        if data.get('has_warnings') == 'Ja' or data.get('legal_issues') == 'Ja':
            summary.extend([
                "🚨 **Wichtiger Hinweis:** Da du bereits Mahnungen oder rechtliche Konsequenzen erwähnst, empfehle ich dringend, professionelle Hilfe in Anspruch zu nehmen.",
                "",
                f"📞 {EMERGENCY_RESOURCES['debt_advice']}",
                f"📞 {EMERGENCY_RESOURCES['crisis']}",
                ""
            ])
        
        # Add next steps
        summary.extend([
            "📌 **Nächste Schritte:**",
            "1. Erstelle eine detaillierte Auflistung aller Gläubiger und Forderungen",
            "2. Erstelle ein Haushaltsbuch, um deine Ausgaben zu tracken",
            "3. Vereinbare einen Termin bei einer Schuldnerberatung",
            "",
            "Womit möchtest du anfangen?"
        ])
        
        return "\n".join(summary)
    
    except (ValueError, TypeError) as e:
        print(f"Error generating summary: {e}")
        return """
        Vielen Dank für deine Angaben. Hier ist eine erste Einschätzung deiner Situation:
        
        • Monatliches Einkommen: {}
        • Wohnkosten (Miete & NK): {}
        • Sonstige Fixkosten: {}
        • Geschätzte Schulden: {}
        • Anzahl der Gläubiger: {}
        
        Basierend auf deinen Angaben empfehle ich dir dringend, eine professionelle Schuldnerberatung aufzusuchen. 
        
        Möchtest du, dass ich dir dabei helfe, dich auf das Beratungsgespräch vorzubereiten?
        """.format(
            data.get('income', 'nicht angegeben'),
            data.get('rent', 'nicht angegeben'),
            data.get('expenses', 'nicht angegeben'),
            data.get('total_debt', 'nicht angegeben'),
            data.get('creditors_count', 'nicht angegeben')
        )

def get_acknowledgment() -> str:
    """Return a random acknowledgment phrase."""
    acknowledgments = [
        "Verstehe.",
        "Ich verstehe.",
        "Danke für diese Information.",
        "Alles klar.",
        "Danke, dass du das mit mir teilst.",
        "Ich höre dir zu.",
        "Danke für deine Offenheit.",
        "Das ist gut zu wissen.",
        "Ich verstehe deine Situation.",
        "Danke für deine Antwort."
    ]
    return random.choice(acknowledgments)

def get_empathy_phrase() -> str:
    """Return a random empathy phrase."""
    empathy_phrases = [
        "Das klingt wirklich herausfordernd.",
        "Ich kann mir vorstellen, dass das belastend ist.",
        "Das ist wirklich nicht einfach.",
        "Ich verstehe, dass dich das belastet.",
        "Das klingt nach einer schwierigen Situation.",
        "Das tut mir leid zu hören.",
        "Ich kann verstehen, dass dich das belastet.",
        "Das ist wirklich nicht leicht.",
        "Ich höre, dass dich das sehr beschäftigt.",
        "Das klingt nach einer großen Herausforderung."
    ]
    return random.choice(empathy_phrases)

def get_transition_phrase() -> str:
    """Return a random transition phrase."""
    transitions = [
        "Lass uns gemeinsam schauen, wie wir das angehen können.",
        "Ich helfe dir gerne weiter.",
        "Lass uns das Schritt für Schritt angehen.",
        "Ich bin für dich da, um zu helfen.",
        "Gemeinsam finden wir einen Weg.",
        "Lass uns das systematisch angehen.",
        "Ich unterstütze dich dabei.",
        "Zusammen schaffen wir das.",
        "Lass uns das Stück für Stück durchgehen.",
        "Ich begleite dich durch diesen Prozess."
    ]
    return random.choice(transitions)

def update_conversation(conversation_id: str, user_input: str, conversation_state: dict) -> dict:
    """Update conversation state based on user input."""
    # Initialize conversation if this is the first message
    if 'step' not in conversation_state:
        conversation_state['step'] = 0
        conversation_state['data'] = {}
        conversation_state['previous_responses'] = []
        return {
            'response': get_next_question(conversation_state),
            'state': conversation_state
        }
    
    current_step = conversation_state.get('step', 0)
    
    # Store user's response for context
    if 'previous_responses' not in conversation_state:
        conversation_state['previous_responses'] = []
    
    # Add user input to conversation history (last 3 messages for context)
    conversation_state['previous_responses'] = (conversation_state.get('previous_responses', []) + [user_input])[-3:]
    
    # Handle emergency situations first
    emergency_phrases = {
        'selbstmord': "Das klingt sehr besorgniserregend. Bitte wende dich sofort an die Telefonseelsorge unter 0800 111 0 111. Du bist nicht allein und es gibt Menschen, die dir helfen können.",
        'selbstmorden': "Das klingt sehr besorgniserregend. Bitte wende dich sofort an die Telefonseelsorge unter 0800 111 0 111. Du bist nicht allein und es gibt Menschen, die dir helfen können.",
        'umbringen': "Das klingt sehr beunruhigend. Bitte kontaktiere umgehend eine Vertrauensperson oder die Telefonseelsorge unter 0800 111 0 111.",
        'sterben': "Es tut mir leid zu hören, dass du solche Gedanken hast. Bitte wende dich an jemanden, der dir helfen kann, zum Beispiel die Telefonseelsorge unter 0800 111 0 111.",
        'leben beenden': "Das klingt sehr belastend. Bitte wende dich sofort an eine Person deines Vertrauens oder die Telefonseelsorge unter 0800 111 0 111. Du bist nicht allein.",
        'kann nicht mehr': "Ich höre, wie schwer es dir gerade fällt. Es ist wichtig, dass du dir jetzt Hilfe holst. Möchtest du, dass ich dir dabei helfe, Unterstützung zu finden?",
        'sinnlos': "Es tut mir leid, dass du dich so fühlst. Manchmal kann es helfen, mit jemandem zu sprechen. Die Telefonseelsorge ist rund um die Uhr erreichbar unter 0800 111 0 111.",
        'aufgeben': "Ich verstehe, dass du dich überfordert fühlst. Aber es gibt immer einen Ausweg, auch wenn du ihn gerade nicht siehst. Möchtest du, dass wir gemeinsam nach Lösungen suchen?",
        'keinen Ausweg': "Es tut mir leid zu hören, dass du dich so fühlst. Manchmal kann ein Gespräch mit einer neutralen Person helfen. Die Telefonseelsorge ist unter 0800 111 0 111 erreichbar.",
        'kein Sinn mehr': "Ich höre, wie verzweifelt du bist. Bitte glaub mir, dass es Menschen gibt, die dir helfen können. Möchtest du, dass ich dir dabei helfe, Unterstützung zu finden?"
    }
    
    for phrase, response in emergency_phrases.items():
        if phrase in user_input.lower():
            return {
                'response': f"{get_empathy_phrase()} {response} Möchtest du, dass ich dir dabei helfe, Unterstützung zu finden?",
                'state': conversation_state
            }
    
    # Handle user input for the current step
    if current_step < len(CONVERSATION_FLOW):
        current_question = CONVERSATION_FLOW[current_step]
        field_type = current_question.get('type', 'text')
        validation = current_question.get('validation')
        options = current_question.get('options')
        
        # Validate input
        is_valid, result = validate_input(
            user_input, 
            field_type=field_type,
            validation=validation,
            options=options
        )
        
        if not is_valid:
            # Show validation error and ask the same question again
            return {
                'response': f"{result}\n\n{current_question['question']}\n\n({current_question.get('hint', '')})",
                'state': conversation_state
            }
        
        # Store the validated input
        conversation_state['data'][current_question['key']] = result
        conversation_state['step'] += 1
    
    # Get next question or provide summary
    next_question = get_next_question(conversation_state)
    
    if next_question:
        # Add acknowledgment and empathy based on user's last input
        user_last_message = conversation_state['previous_responses'][-1] if conversation_state['previous_responses'] else ""
        
        # Check if the last message was short (likely just an answer to our question)
        is_short_response = len(user_last_message.split()) <= 5
        
        if is_short_response:
            response = f"{get_acknowledgment()} {next_question}"
        else:
            # For longer responses, show more empathy
            response = f"{get_empathy_phrase()} {get_transition_phrase()} {next_question}"
        
        return {
            'response': response,
            'state': conversation_state
        }
    else:
        # Conversation complete - generate and return summary
        summary = generate_financial_summary(conversation_state['data'])
        
        # Add a follow-up question
        follow_up = ""
        
        # Check for emergency situations
        if (conversation_state['data'].get('has_warnings') == 'Ja' or 
            conversation_state['data'].get('legal_issues') == 'Ja'):
            follow_up = (
                "\n\n🚨 **Wichtiger Hinweis:** Da du bereits Mahnungen oder rechtliche Konsequenzen "
                "erwähnst, empfehle ich dringend, professionelle Hilfe in Anspruch zu nehmen. "
                "Möchtest du, dass ich dir dabei helfe, einen Termin bei einer Schuldnerberatung zu vereinbaren?"
            )
        else:
            follow_up = (
                "\n\nMöchtest du, dass ich dir dabei helfe, "
                "eine detaillierte Gläubigerliste zu erstellen oder ein Haushaltsbuch anzulegen?"
            )
        
        return {
            'response': summary + follow_up,
            'state': conversation_state
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_input = data.get('message', '').strip()
        conversation_id = data.get('conversation_id', f'conv_{datetime.now().strftime("%Y%m%d%H%M%S")}_{os.urandom(4).hex()}')
        
        # Initialize conversation if it doesn't exist
        if conversation_id not in conversations:
            conversations[conversation_id] = {'step': 0, 'data': {}, 'start_time': datetime.now().isoformat()}
        
        conversation_state = conversations[conversation_id]
        
        # Process the message and get response
        result = update_conversation(conversation_id, user_input, conversation_state)
        
        # Update conversation state from result if it exists, otherwise keep the current state
        if 'state' in result:
            conversation_state = result['state']
            conversations[conversation_id] = conversation_state
        
        # Update last activity timestamp
        conversation_state['last_activity'] = datetime.now().isoformat()
        
        # Clean up old conversations (older than 24 hours)
        cleanup_old_conversations()
        
        return jsonify({
            'response': result['response'],
            'conversation_id': conversation_id,
            'status': 'success'
        })
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'response': 'Es ist ein Fehler aufgetreten. Bitte versuche es später noch einmal.',
            'conversation_id': conversation_id,
            'status': 'error'
        }), 500

def cleanup_old_conversations():
    """Remove conversations older than 24 hours."""
    now = datetime.now()
    to_delete = []
    
    for conv_id, conv_data in conversations.items():
        last_activity = conv_data.get('last_activity', conv_data.get('start_time'))
        if not last_activity:
            continue
            
        if isinstance(last_activity, str):
            try:
                last_activity = datetime.fromisoformat(last_activity)
            except (ValueError, TypeError):
                continue
        
        if (now - last_activity) > timedelta(hours=24):
            to_delete.append(conv_id)
    
    for conv_id in to_delete:
        del conversations[conv_id]

if __name__ == '__main__':
    # Configure Flask app
    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-123')
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # Create necessary directories
    os.makedirs('instance/sessions', exist_ok=True)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5000)
