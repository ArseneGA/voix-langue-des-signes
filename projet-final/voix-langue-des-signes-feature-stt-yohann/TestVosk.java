import java.io.IOException;
import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.TargetDataLine;
import org.vosk.Model;
import org.vosk.Recognizer;

public class TestVosk {

    public static void main(String[] args) {
        
        // --- CONFIGURATION DU CHEMIN DU MODÈLE ---
        // ⚠️ VERIFIE CE CHEMIN ! 
        // Si ton dossier s'appelle "vosk-model-fr" ou autre chose, change le nom ici.
        // Il doit pointer vers le dossier qui contient "am", "conf", etc.
        String cheminModele = "stt/model/vosk-model-small-fr-0.22"; 
        // -----------------------------------------

        try {
            System.out.println("⏳ Chargement du modèle (ça peut prendre quelques secondes)...");
            
            // 1. On charge le "Cerveau" (Le modèle de langue)
            // Note : Si ça plante ici, c'est que le chemin 'cheminModele' est faux !
            try (Model model = new Model(cheminModele)) {
                
                // 2. On prépare le "Traducteur"
                Recognizer recognizer = new Recognizer(model, 16000);
                
                // 3. On configure le MICROPHONE
                AudioFormat format = new AudioFormat(16000, 16, 1, true, false);
                DataLine.Info info = new DataLine.Info(TargetDataLine.class, format);
                
                if (!AudioSystem.isLineSupported(info)) {
                    System.err.println("❌ Erreur : Aucun microphone détecté !");
                    return;
                }

                TargetDataLine microphone = (TargetDataLine) AudioSystem.getLine(info);
                microphone.open(format);
                microphone.start();

                System.out.println("\n🎤 CA MARCHE ! PARLE DANS TON MICRO (Dis 'Bonjour')...");
                System.out.println("(Appuie sur le carré rouge Stop pour arrêter)\n");

                // 4. BOUCLE D'ÉCOUTE
                byte[] buffer = new byte[4096];
                int nbytes;
                
                while ((nbytes = microphone.read(buffer, 0, buffer.length)) >= 0) {
                    if (recognizer.acceptWaveForm(buffer, nbytes)) {
                        String resultat = recognizer.getResult();
                        System.out.println("🗣️ Tu as dit : " + resultat);
                    }
                }
                
                microphone.close();
            }
        } catch (IOException e) {
            System.err.println("❌ ERREUR DE DOSSIER : Impossible de trouver le modèle Vosk !");
            System.err.println("   -> Le code cherche ici : " + new java.io.File(cheminModele).getAbsolutePath());
            System.err.println("   -> Vérifie que le dossier 'model' est bien dans 'stt'");
        } catch (Exception e) {
            System.err.println("❌ ERREUR TECHNIQUE :");
            e.printStackTrace();
        }
    }
}