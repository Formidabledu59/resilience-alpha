import { List, Prose, Section } from './Prose.jsx'

export default function Confidentialite() {
  return (
    <Prose title="Confidentialité et données personnelles" updated="19 octobre 2026">
      <p>
        Resilience Alpha est un démonstrateur pédagogique réalisé par le groupe 16 du workshop EPSI 2026-27.
        Il fonctionne uniquement sur le réseau de laboratoire du groupe. Cette page explique, conformément au
        Règlement général sur la protection des données (RGPD), quelles données sont traitées et pourquoi.
      </p>

      <Section title="Responsable du traitement">
        <p>
          L'équipe projet du groupe 16. Pour toute question, ouvrez une demande sur le dépôt du projet ou contactez
          l'équipe pendant le workshop.
        </p>
      </Section>

      <Section title="Données traitées">
        <List
          items={[
            "Identifiant de connexion fictif (demo) : aucune personne réelle n'est associée à un compte.",
            'Transactions fictives entre comptes de démonstration : montants, comptes, date, statut.',
            "Journaux techniques du serveur : page demandée, code de réponse, durée, navigateur. Le frontal n'enregistre pas votre adresse IP.",
            "Journaux de sécurité du pare-feu applicatif (WAF) : ils peuvent contenir l'adresse IP de l'appareil, pour détecter et bloquer les attaques.",
          ]}
        />
        <p>Aucune donnée bancaire réelle n'est collectée. Ne saisissez jamais de vraies informations personnelles.</p>
      </Section>

      <Section title="Finalités et base légale">
        <List
          items={[
            'Faire fonctionner la démonstration de paiement (exécution du service).',
            'Détecter les attaques, rétablir le service et le prouver (intérêt légitime : sécurité du système).',
            "Mesurer l'audience de façon anonyme, à partir des journaux du serveur, sans cookie ni traceur.",
          ]}
        />
      </Section>

      <Section title="Durée de conservation">
        <p>
          Les journaux sont conservés 7 jours, puis supprimés automatiquement. Les données de démonstration sont
          effacées à chaque remise à zéro de la plateforme.
        </p>
      </Section>

      <Section title="Destinataires">
        <p>
          Les données restent sur l'ordinateur hôte du laboratoire. Elles ne sont ni vendues, ni transmises à des
          tiers, ni envoyées vers un service en ligne.
        </p>
      </Section>

      <Section title="Cookies et stockage local">
        <p>
          Ce site ne dépose aucun cookie. Il utilise seulement le stockage du navigateur pour deux usages
          strictement nécessaires, qui ne demandent pas de consentement :
        </p>
        <List
          items={[
            "La session de connexion, effacée à la fermeture de l'onglet.",
            "Le fait d'avoir lu le bandeau d'information, pour ne pas le réafficher.",
          ]}
        />
      </Section>

      <Section title="Vos droits">
        <p>
          Vous disposez d'un droit d'accès, de rectification, d'effacement, de limitation et d'opposition. Vous
          pouvez aussi introduire une réclamation auprès de la CNIL (cnil.fr).
        </p>
      </Section>
    </Prose>
  )
}
