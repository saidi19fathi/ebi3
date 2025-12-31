# Ebi3 - Plateforme Logistique Transfrontalière

Site Django pour la vente, l'achat et le transport d'objets entre pays.

## Technologies
- Django 6.0
- Bootstrap 5
- PostgreSQL/SQLite
- Font Awesome

## Fonctionnalités
- Système d'annonces
- Transporteurs professionnels/particuliers
- Messagerie interne
- Système de favoris
- Recherche avancée

## Installation
1. Clonez le projet
2. Créez un environnement virtuel
3. Installez les dépendances : `pip install -r requirements.txt`
4. Configurez les variables d'environnement
5. Lancez les migrations : `python manage.py migrate`
6. Créez un superuser : `python manage.py createsuperuser`
7. Lancez le serveur : `python manage.py runserver`

## Structure du projet ebi3/
├── ads/ # Application annonces
├── carriers/ # Application transporteurs
├── core/ # Application principale
├── users/ # Application utilisateurs
└── ebi3/ # Configuration Django

## Auteur
saidi19fathi
