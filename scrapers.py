import requests
from bs4 import BeautifulSoup
import json
import os # <-- ¡Importante! Para leer las variables de entorno

# --- FUNCIÓN PARA SCRAPING DE GLASSDOOR USANDO SCRAPINGBEE ---

def scrape_glassdoor_jobs(keywords, location="Mexico"):
    """
    Realiza scraping de ofertas de empleo en Glassdoor utilizando ScrapingBee
    y activando el renderizado de JavaScript.
    """
    print(f"  -> Iniciando scraping en Glassdoor para '{keywords}' en '{location}' vía ScrapingBee...")

    api_key = os.environ.get("SCRAPINGBEE_API_KEY")
    if not api_key:
        print("  -> ERROR: La variable de entorno SCRAPINGBEE_API_KEY no está definida.")
        return []

    target_url = f"https://www.glassdoor.com/Job/{location.lower()}-{keywords.replace(' ', '-')}-jobs.htm"

    api_endpoint = 'https://app.scrapingbee.com/api/v1/'
    params = {
        'api_key': api_key,
        'url': target_url,
        'render_js': 'true' # <-- CAMBIO CLAVE: Activamos JavaScript
    }

    try:
        response = requests.get(api_endpoint, params=params, timeout=120) # Aumentamos el timeout
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')
        job_listings = soup.select('li.react-job-listing') # Esta clase puede necesitar ajuste

        if not job_listings:
            # Intentamos con otra posible clase si la primera falla
            job_listings = soup.select('li[class*="JobCard"]')
            if not job_listings:
                 print("  -> Petición exitosa, pero no se encontraron ofertas.")
                 return []

        extracted_jobs = []
        for job in job_listings:
            # Aquí la lógica de extracción, que puede necesitar ajustes si las clases internas cambian
            title_element = job.select_one('a[data-test="job-title"], a[class*="JobCard__title"]')
            company_element = job.select_one('span[data-test="employer-name"], span[class*="EmployerProfile__employerName"]')
            location_element = job.select_one('div[data-test="location"], div[class*="JobCard__location"]')
            url_element = title_element

            if all([title_element, company_element, location_element, url_element]):
                job_data = {
                    "title": title_element.get_text(strip=True),
                    "company_name": company_element.get_text(strip=True),
                    "location": location_element.get_text(strip=True),
                    "source_url": "https://www.glassdoor.com" + url_element['href']
                }
                extracted_jobs.append(job_data)

        print(f"  -> Scraping finalizado. Se encontraron {len(extracted_jobs)} ofertas.")
        return extracted_jobs

    except requests.exceptions.RequestException as e:
        print(f"  -> ERROR: Ocurrió un error en la petición a ScrapingBee: {e}")
        return []
    except Exception as e:
        print(f"  -> ERROR: Ocurrió un error inesperado durante el scraping: {e}")
        return []

# --- BLOQUE DE PRUEBA INDEPENDIENTE ---
if __name__ == "__main__":
    from dotenv import load_dotenv
    # Cargamos las variables de .env para que la prueba funcione
    load_dotenv()

    print("--- Realizando prueba del scraper de Glassdoor (vía ScrapingBee) ---")
    test_keywords = "Business Analyst"
    test_location = "Mexico"
    found_jobs = scrape_glassdoor_jobs(test_keywords, test_location)

    if found_jobs:
        print(f"\nResultados de la prueba para '{test_keywords}':")
        print(json.dumps(found_jobs, indent=2, ensure_ascii=False))
    else:
        print(f"\nNo se encontraron trabajos para '{test_keywords}'.")

    print("\n--- Prueba finalizada ---")