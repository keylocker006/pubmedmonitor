import os
import sys
import threading
import time
from datetime import datetime

'''from kivy.core.text import LabelBase
from kivy.resources import resource_find

# Register fonts FIRST (b3efore any Kivy widgets are created)
LabelBase.register(
    name='NotoColorEmoji',
    fn_regular=resource_find('fonts/NotoColorEmoji.ttf')
)'''

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import mainthread
from androidstorage4kivy import SharedStorage


# Import your core script
import pubmed_monitor as pm


class MobileMonitor(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=20, spacing=15, **kwargs)
        
        # Header
        self.add_widget(Label(
            text="🔬 PubMed Monitor",
            #font_name=['Roboto', 'NotoColorEmoji'],
            font_size="18dp", 
            size_hint_y=None, 
            height=45,
            bold=True,
            
        ))
        
        # Search Term Input
        self.add_widget(Label(text="Enter Search Keyword:", size_hint_y=None, height=40, halign="left"))
        self.term_input = TextInput(
            text="", 
            multiline=False, 
            size_hint_y=None, 
            height=45,
            hint_text="e.g., leukemia, anemia, diabetes, cancer"
        )
        self.add_widget(self.term_input)
        
        # Max Results Input
        self.add_widget(Label(text="Max Results:", size_hint_y=None, height=40, halign="left"))
        self.max_input = TextInput(
            text="", 
            multiline=False, 
            size_hint_y=None, 
            height=45,
            hint_text="e.g., 10, 20, 100"
        )
        self.add_widget(self.max_input)
        
        # Run Button
        self.btn_run = Button(
            text="Start Download & Tracking", 
            size_hint_y=None, 
            height=45,
            background_color=(0.1, 0.5, 0.9, 1)
        )
        self.btn_run.bind(on_press=self.start_pipeline)
        self.add_widget(self.btn_run)
        
        # Scrollable Terminal Log
        self.scroll = ScrollView(size_hint=(1, 1))
        self.log_label = Label(
            text="Ready to analyze.\n", 
            size_hint_y=None, 
            halign="left", 
            valign="top",
            font_name="Roboto"
        )
        # Ensure text wraps inside the scroll view correctly
        self.log_label.bind(width=lambda *x: self.log_label.setter("text_size")(self.log_label, (self.log_label.width, None)))
        self.log_label.bind(texture_size=lambda *x: self.log_label.setter("height")(self.log_label, self.log_label.texture_size[1]))
        
        self.scroll.add_widget(self.log_label)
        self.add_widget(self.scroll)

    def start_pipeline(self, instance):
        """Disables the run button and kicks off the background thread."""
        self.btn_run.disabled = True
        self.log_label.text = "Initializing pipeline...\n"
        
        term = self.term_input.text or "hematology"
        try:
            max_r = int(self.max_input.text or 10)
        except ValueError:
            self.update_log("Invalid max results. Defaulting to 10.")
            max_r = 10
            
        # Spawn asynchronous thread to prevent UI freezing
        threading.Thread(target=self.run_pipeline_async, args=(term, max_r)).start()

    @mainthread
    def update_log(self, text):
        """Thread-safe UI updater. Appends log text onto the screen."""
        self.log_label.text += f"{text}\n"

    @mainthread
    def enable_button(self):
        """Thread-safe UI utility to re-enable execution button."""
        self.btn_run.disabled = False

    def run_pipeline_async(self, term, max_r):
        """Main execution engine running outside the main thread."""
        try:
            # Set up sandboxed directory structures for Android
            app_instance = App.get_running_app()
            sandboxed_dir = app_instance.user_data_dir
            
            # Point CSV and PDF folders inside the sandbox
            csv_path = os.path.join(sandboxed_dir, "collection.csv")
            download_dir = os.path.join(sandboxed_dir, "papers")
            
            self.update_log(f"Database Sandbox: {sandboxed_dir}")
            self.update_log("=" * 40)
            
            # 1. Load PMIDs we already have
            existing_pmids = pm.load_existing_pmids(csv_path)
            self.update_log(f"Existing papers in CSV: {len(existing_pmids)}")
            time.sleep(0.4)

            # 2. Search PubMed
            self.update_log(f"Searching PubMed for: '{term}'")
            pmids = pm.search_pubmed(term, days_back=pm.DAYS_BACK, max_results=max_r)
            time.sleep(0.4)

            # 3. Filter duplicates
            new_pmids = [p for p in pmids if p not in existing_pmids]
            self.update_log(f"New papers to process: {len(new_pmids)}")

            if not new_pmids:
                self.update_log("\nCollection is fully up to date!")
                return

            # 4. Fetch details
            self.update_log(f"Fetching metadata for {len(new_pmids)} articles...")
            articles = pm.fetch_article_details(new_pmids)
            time.sleep(0.4)

            all_new_articles = []
            download_count = 0

                       # 5. Process and Download PDFs
            for article in articles:
                article["search_term"] = term
                article["pdf_downloaded"] = "No"
                article["pdf_filename"] = ""
                article["added_date"] = datetime.now().strftime("%Y-%m-%d")

                if article["pmc_id"]:
                    self.update_log(f"Checking PDF for {article['pmc_id']}...")
                    time.sleep(0.4)

                    pdf_url = pm.check_pdf_availability(article["pmc_id"])

                    if pdf_url:
                        filename = f"{article['pmc_id']}.pdf"
                        try:
                            self.update_log(f"-> Downloading {filename} to sandbox...")
                            # 1. Download file to private sandbox first
                            private_path = pm.download_pdf(pdf_url, filename, download_dir)
                            
                            # 2. Safely copy the file to the shared public Downloads folder
                            self.update_log(f"-> Exporting {filename} to public Downloads...")
                            shared_storage = SharedStorage()
                            shared_uri = shared_storage.copy_to_shared(private_path, collection="Downloads")
                            
                            if shared_uri:
                                self.update_log(f"   Saved publicly: {filename}")
                                article["pdf_downloaded"] = "Yes"
                                article["pdf_filename"] = filename
                                download_count += 1
                            else:
                                self.update_log("   Warning: Could not copy to public Downloads.")
                                
                        except Exception as e:
                            self.update_log(f"Download failed: {e}")

                all_new_articles.append(article)

            # 6. Save to CSV sandbox
            if all_new_articles:
                self.update_log(f"Writing entries to collection.csv...")
                pm.save_to_csv(all_new_articles, csv_path)
                self.update_log("=" * 40)
                self.update_log(f"Added {len(all_new_articles)} entries to CSV database.")
                self.update_log(f"Successfully downloaded {download_count} PDFs.")
            else:
                self.update_log("\nNo new records to append.")

        except Exception as e:
            self.update_log(f"\nCritical Error: {e}")
        finally:
            self.enable_button()

class MonitorApp(App):
    def build(self):
        return MobileMonitor()

if __name__ == "__main__":
    MonitorApp().run()