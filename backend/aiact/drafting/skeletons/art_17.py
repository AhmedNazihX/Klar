"""The quality management system skeleton (Art. 17): one section per aspect Art. 17(1) says the
system includes at least, points (a) to (m). The duty it answers is Art. 16(c).

Art. 17(2) lets an SME or a small mid-cap implement these in proportion to its size; it still
lists every aspect, so the skeleton is the same for every company.
"""

from aiact.drafting.models import DocumentKind, SectionStatus
from aiact.drafting.skeletons.common import PREFILLED, ask, required
from aiact.drafting.templates import DE, EN, DocumentTemplate

ART_17_SKELETON = DocumentTemplate(
    id="art_17_quality_management",
    article="art:16:c",
    kind=DocumentKind.SKELETON,
    title={EN: "Quality management system (Art. 17)", DE: "Qualitätsmanagementsystem (Art. 17)"},
    sections=(
        *PREFILLED,
        required(
            "compliance_strategy",
            ("Strategy for regulatory compliance", "Konzept zur Einhaltung der Vorschriften"),
            "art:17:1:a",
            ask(
                "compliance_strategy",
                "What is your strategy for regulatory compliance, including conformity "
                "assessment and the management of changes to the system?",
                "Wie sieht Ihr Konzept zur Einhaltung der Regulierungsvorschriften aus, "
                "einschließlich der Konformitätsbewertung und des Managements von Änderungen am "
                "System?",
            ),
        ),
        required(
            "design_control",
            ("Design, design control and verification", "Entwurf, Entwurfskontrolle und -prüfung"),
            "art:17:1:b",
            ask(
                "design_control",
                "Which techniques, procedures and systematic actions do you use to design the "
                "system and to control and verify its design?",
                "Welche Techniken, Verfahren und systematischen Maßnahmen nutzen Sie für den "
                "Entwurf, die Entwurfskontrolle und die Entwurfsprüfung des Systems?",
            ),
        ),
        required(
            "development_quality",
            (
                "Development, quality control and assurance",
                "Entwicklung, Qualitätskontrolle und -sicherung",
            ),
            "art:17:1:c",
            ask(
                "development_quality",
                "Which techniques, procedures and systematic actions do you use for "
                "development, quality control and quality assurance?",
                "Welche Techniken, Verfahren und systematischen Maßnahmen nutzen Sie für "
                "Entwicklung, Qualitätskontrolle und Qualitätssicherung?",
            ),
        ),
        required(
            "test_procedures",
            ("Examination, test and validation", "Untersuchung, Test und Validierung"),
            "art:17:1:d",
            ask(
                "test_procedures",
                "Which examination, test and validation procedures do you carry out before, "
                "during and after development, and how often?",
                "Welche Untersuchungs-, Test- und Validierungsverfahren führen Sie vor, während "
                "und nach der Entwicklung durch, und wie häufig?",
            ),
        ),
        required(
            "technical_specifications",
            ("Technical specifications and standards", "Technische Spezifikationen und Normen"),
            "art:17:1:e",
            ask(
                "technical_specifications",
                "Which technical specifications and standards do you apply, and where the "
                "harmonised standards don't cover every requirement, how do you meet it?",
                "Welche technischen Spezifikationen und Normen wenden Sie an, und wie erfüllen "
                "Sie die Anforderungen, die harmonisierte Normen nicht abdecken?",
            ),
            waits_for=SectionStatus.NEEDS_EVIDENCE,
        ),
        required(
            "data_management",
            ("Data management", "Datenmanagement"),
            "art:17:1:f",
            ask(
                "data_management",
                "Which systems and procedures govern your data management, from acquisition and "
                "labelling to storage and retention?",
                "Welche Systeme und Verfahren regeln Ihr Datenmanagement, von der Gewinnung und "
                "Kennzeichnung bis zur Speicherung und Aufbewahrung?",
            ),
        ),
        required(
            "risk_management",
            ("Risk management system", "Risikomanagementsystem"),
            "art:17:1:g",
            ask(
                "risk_management_document",
                "Which document sets out your risk management system under Art. 9?",
                "In welchem Dokument ist Ihr Risikomanagementsystem nach Art. 9 festgelegt?",
            ),
            waits_for=SectionStatus.TO_FILL_IN,
        ),
        required(
            "post_market_monitoring",
            ("Post-market monitoring", "Beobachtung nach dem Inverkehrbringen"),
            "art:17:1:h",
            ask(
                "post_market_monitoring",
                "How do you set up, run and maintain post-market monitoring (Art. 72)?",
                "Wie richten Sie die Beobachtung nach dem Inverkehrbringen (Art. 72) ein, wie "
                "wenden Sie sie an und wie erhalten Sie sie aufrecht?",
            ),
        ),
        required(
            "incident_reporting",
            ("Reporting serious incidents", "Meldung schwerwiegender Vorfälle"),
            "art:17:1:i",
            ask(
                "incident_reporting",
                "What is your procedure for reporting a serious incident (Art. 73)?",
                "Wie sieht Ihr Verfahren zur Meldung eines schwerwiegenden Vorfalls (Art. 73) aus?",
            ),
        ),
        required(
            "communication",
            ("Communication", "Kommunikation"),
            "art:17:1:j",
            ask(
                "communication",
                "How do you handle communication with authorities, notified bodies, other "
                "operators, customers and other interested parties?",
                "Wie handhaben Sie die Kommunikation mit Behörden, notifizierten Stellen, "
                "anderen Akteuren, Kunden und sonstigen interessierten Kreisen?",
            ),
        ),
        required(
            "record_keeping",
            ("Record-keeping", "Aufzeichnung"),
            "art:17:1:k",
            ask(
                "record_keeping",
                "Which systems and procedures keep records of all relevant documentation and "
                "information?",
                "Mit welchen Systemen und Verfahren zeichnen Sie sämtliche einschlägige "
                "Dokumentation und Informationen auf?",
            ),
        ),
        required(
            "resource_management",
            ("Resource management", "Ressourcenmanagement"),
            "art:17:1:l",
            ask(
                "resource_management",
                "How do you manage resources, including security of supply?",
                "Wie managen Sie Ressourcen, einschließlich der Versorgungssicherheit?",
            ),
        ),
        required(
            "accountability",
            ("Accountability", "Rechenschaftsrahmen"),
            "art:17:1:m",
            ask(
                "accountability",
                "Who in management and among other staff is responsible for each of these aspects?",
                "Wer in der Leitung und im sonstigen Personal ist für jeden dieser Aspekte "
                "verantwortlich?",
            ),
        ),
    ),
)
