import { List, Prose, Section } from './Prose.jsx'

export default function Cgu() {
  return (
    <Prose title="Conditions générales d'utilisation" updated="19 octobre 2026">
      <Section title="1. Objet">
        <p>
          Les présentes conditions encadrent l'utilisation de Resilience Alpha, démonstrateur pédagogique de
          plateforme de paiement réalisé dans le cadre du workshop EPSI 2026-27 (groupe 16).
        </p>
      </Section>

      <Section title="2. Nature du service">
        <List
          items={[
            "Le service est fictif : aucun paiement réel n'est effectué et aucun argent réel ne circule.",
            'Les comptes, identifiants et montants sont des données de démonstration.',
            "Le service n'est accessible que sur le réseau de laboratoire du groupe.",
          ]}
        />
      </Section>

      <Section title="3. Utilisation autorisée">
        <p>
          L'utilisation est réservée à la démonstration et à l'évaluation du projet. Il est interdit d'y saisir des
          données personnelles ou bancaires réelles.
        </p>
      </Section>

      <Section title="4. Tests de sécurité">
        <p>
          Des attaques contrôlées font partie de la démonstration. Elles sont strictement limitées au système du
          groupe 16 et au réseau du laboratoire. Toute attaque visant un autre système est interdite.
        </p>
      </Section>

      <Section title="5. Disponibilité">
        <p>
          Le service peut être interrompu à tout moment, notamment pendant les démonstrations d'incident. Sa
          disponibilité n'est pas garantie.
        </p>
      </Section>

      <Section title="6. Responsabilité">
        <p>
          Le démonstrateur est fourni en l'état, sans garantie. Il n'est pas destiné à un usage en production.
        </p>
      </Section>

      <Section title="7. Données personnelles">
        <p>
          Le traitement des données est décrit sur la page Confidentialité et données personnelles.
        </p>
      </Section>
    </Prose>
  )
}
