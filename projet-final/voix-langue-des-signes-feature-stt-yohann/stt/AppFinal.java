package stt; // ⚠️ LIGNE OBLIGATOIRE (Correction de l'erreur Package)

import java.io.File;
import java.util.HashMap;
import java.util.Map;
import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.TargetDataLine;
import org.vosk.Model;
import org.vosk.Recognizer;

public class AppFinal {

    // --- 1. CONFIGURATION ---
    // Le dossier où sont tes fichiers .sigml
    // Note : On utilise "stt/" car c'est ton dossier de base
    private static final String DOSSIER_BDD = "stt/database_signes/";
    
    // Le dossier de ton modèle (Cerveau)
    // ⚠️ VÉRIFIE CE CHEMIN SI ÇA PLANTE ! (Il doit correspondre à ton dossier extrait)
    private static final String CHEMIN_MODELE = "stt/model/vosk-model-small-fr-0.22"; 

    // Notre dictionnaire (Cerveau des signes)
    private static Map<String, String> dictionnaire = new HashMap<>();

    public static void main(String[] args) {
        
        // J'ai supprimé la ligne "LibVosk.setLogLevel" pour corriger ton erreur WARNING.
        
        // --- 2. REMPLISSAGE DU DICTIONNAIRE ---
        // On associe les mots (en minuscules) aux fichiers
        dictionnaire.put("accepter", "Accept1n.LSF");
        dictionnaire.put("étranger", "Abroad1n.LSF");
        dictionnaire.put("un peu",   "A_little1n.LSF");
        
        // -------------------------------------

        try {
            System.out.println("⏳ Chargement du cerveau (Vosk)...");
            
            // Chargement du modèle
            try (Model model = new Model(CHEMIN_MODELE)) {
                Recognizer recognizer = new Recognizer(model, 16000);
                
                // Config Micro
                AudioFormat format = new AudioFormat(16000, 16, 1, true, false);
                DataLine.Info info = new DataLine.Info(TargetDataLine.class, format);
                
                if (!AudioSystem.isLineSupported(info)) {
                    System.out.println("❌ Erreur : Micro non détecté !");
                    return;
                }

                TargetDataLine microphone = (TargetDataLine) AudioSystem.getLine(info);
                microphone.open(format);
                microphone.start();

                System.out.println("\n===========================================");
                System.out.println("🎤 PRÊT ! Dis un de ces mots :");
                System.out.println("   -> 'Accepter'");
                System.out.println("   -> 'Etranger'");
                System.out.println("   -> 'Un peu'");
                System.out.println("===========================================\n");

                byte[] buffer = new byte[4096];
                int nbytes;
                
                // Boucle infinie : l'ordi écoute tout le temps
                while ((nbytes = microphone.read(buffer, 0, buffer.length)) >= 0) {
                    if (recognizer.acceptWaveForm(buffer, nbytes)) {
                        String resultatJson = recognizer.getResult();
                        verifierMotsCles(resultatJson);
                    }
                }
            }
        } catch (Exception e) {
            System.out.println("❌ ERREUR : " + e.getMessage());
            e.printStackTrace();
        }
    }

    // Fonction qui analyse ce que tu as dit et cherche le fichier
    public static void verifierMotsCles(String phraseEntendue) {
        // On met tout en minuscule pour comparer facilement
        phraseEntendue = phraseEntendue.toLowerCase();

        // On parcourt tout notre dictionnaire
        for (String motCle : dictionnaire.keySet()) {
            
            // Si la phrase contient le mot (ex: "je veux accepter" contient "accepter")
            if (phraseEntendue.contains(motCle)) {
                System.out.println("\n🗣️ J'ai entendu : " + motCle.toUpperCase());
                
                // On cherche le fichier
                String nomFichier = dictionnaire.get(motCle);
                File fichier = new File(DOSSIER_BDD + nomFichier + ".sigml");

                if (fichier.exists()) {
                    System.out.println("✅ FICHIER TROUVÉ ! -> " + fichier.getName());
                    System.out.println("🚀 ACTION : Lancement de l'avatar... (Simulation)");
                } else {
                    System.out.println("⚠️ Oups, le code marche mais le fichier est introuvable ici :");
                    System.out.println("   " + fichier.getAbsolutePath());
                }
                System.out.println("-------------------------------------------");
            }
        }
    }
}