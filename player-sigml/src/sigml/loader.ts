export async function loadSigmlFromUrl(url: string): Promise<string> {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Impossible de charger le fichier SiGML : ${url}`);
    }
    return await res.text();
  }
  
  // ex : loadSigmlExample("Abroad1n.LSF.sigml")
  export function loadSigmlExample(name: string): Promise<string> {
    return loadSigmlFromUrl(`/assets/sigml-examples/${name}`);
  }
  