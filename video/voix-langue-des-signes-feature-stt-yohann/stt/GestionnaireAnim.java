package stt; // Indispensable car le fichier est dans le dossier 'stt'

import java.io.File;
import java.util.HashMap;
import java.util.Map;

public class GestionnaireAnim {

    // CORRECTION ICI : On précise que les fichiers sont dans le sous-dossier 'stt'
    private static final String DOSSIER_BDD = "stt/database_signes/"; 
    
    // Dictionnaire : Mot Français -> Nom du fichier (SANS le .sigml à la fin)
    private static Map<String, String> dictionnaire = new HashMap<>();

    public static void main(String[] args) {
        System.out.println("--- TEST DE LECTURE ---");
        
        // 1. Configuration des mots (Basé sur tes fichiers réels)
        dictionnaire.put("ACCEPTER", "Accept1n.LSF"); 
        dictionnaire.put("ETRANGER", "Abroad1n.LSF");
        dictionnaire.put("UN PEU", "A_little1n.LSF");
        
        // 2. Lancement des tests
        testerFichier("ACCEPTER");
        testerFichier("ETRANGER");
        testerFichier("UN PEU");
    }

    public static void testerFichier(String mot) {
        String nomFichier = dictionnaire.get(mot);
        
        if (nomFichier == null) {
            System.out.println("❌ Code manquant pour : " + mot);
            return;
        }

        // Construction du chemin complet
        // Cela va donner : stt/database_signes/Accept1n.LSF.sigml
        File f = new File(DOSSIER_BDD + nomFichier + ".sigml");
        
        if (f.exists()) {
            System.out.println(" SUCCÈS : Fichier trouvé pour '" + mot + "'");
            System.out.println("   -> " + f.getAbsolutePath());
        } else {
            System.out.println(" ERREUR : Fichier introuvable.");
            System.out.println("   -> Chemin testé : " + f.getAbsolutePath());
            System.out.println("   -> Vérifie que le dossier 'database_signes' est bien à l'intérieur de 'stt'");
        }
    }
}