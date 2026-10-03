# Design System Farmio

## Objectif

Farmio s'appuie sur un design system léger, cohérent et orienté marketplace agricole B2B. Il privilégie une palette verte premium, des surfaces claires, des cartes lisibles et un système de composants réutilisables pour les écrans Django Templates.

## Palette de couleurs

- primary: `#166534` (green-700)
- primary-hover: `#14532d` (green-800)
- primary-light: `#ecfdf5`
- secondary: `#0f172a`
- success: `#15803d`
- warning: `#d97706`
- danger: `#dc2626`
- info: `#2563eb`
- background: `#f7f9f5`
- surface: `#ffffff`
- border: `#e2e8f0`
- text-primary: `#0f172a`
- text-secondary: `#475569`
- muted: `#64748b`

## Styles de base

- Body: `bg-background text-text-primary antialiased`
- Headings: `font-bold tracking-tight text-slate-900`
- Paragraphs: `text-slate-600 leading-7`
- Labels: `text-xs font-semibold uppercase tracking-[0.2em] text-emerald-700`

## Boutons

- `btn-primary`: action principale
- `btn-secondary`: action secondaire
- `btn-ghost`: action légère de contexte
- `btn-outline`: action d'édition / navigation
- `btn-danger`: suppression / action sensible

## Cartes

- `card-surface`: conteneur standard avec bordure, fond blanc et ombre légère
- `card-dashboard`: carte structurée pour les tableaux de bord
- `stat-card`: carte de métrique avec valeur large et libellé

## Formulaires

- `input-field`: input standardisé
- `textarea-field`: zone de texte standardisée
- `select-field`: select standardisé
- `checkbox-field`: option de formulaire

## États de feedback

- succès: `message-success`
- erreur: `message-error`
- warning: `message-warning`
- info: `message-info`

## Accessibilité

- Contraste suffisant sur fond clair
- Focus visible avec couleur verte
- Boutons et liens visibles et lisibles
- Textes structurés avec titres hiérarchisés
- Images avec `alt` validé

## Responsive

- Mobile-first
- Grille adaptable 1 → 2 → 4 colonnes selon l’écran
- Navigation mobile à 768px et moins
- Courtes lignes de contenu sur les petits écrans

## Règles d’intégration

- Utiliser les classes de composants plutôt que des styles inline
- Ne pas créer de nouvelles couleurs sans les intégrer à cette charte
- Conserver l’usage de Tailwind CLI et Django Templates
- Privilégier les classes réutilisables pour limiter la duplication
- Garder la palette verte comme signature visuelle de Farmio
