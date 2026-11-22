package online.inmodata.app;

import static android.app.ProgressDialog.show;

import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.ListView;
import android.widget.SimpleAdapter;
import android.widget.TextView;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.math.BigDecimal;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.NumberFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import javax.net.ssl.HttpsURLConnection;

/** Shows the public sale catalog, loads the first page on entry, and supports refresh and pagination. */
public class MainActivity extends AppCompatActivity {

    private static final String HOST= "https://inmodata.online";
    private static final String SALES_URL = HOST + "/api/v1/listings/sales/";
    private static final String CATALOG_PREFS = "catalog_filters_v1";
    private final ExecutorService network = Executors.newSingleThreadExecutor();

    private Button loadSales;
    private TextView salesStatus;
    private ListView salesList;
    private Button filterSector;
    private Button filterBudget;
    private Button clearFilters;
    private int activeBudget = 0;// Zero means no maximum; omit it from the API request.
    private static final int[] BUDGETS = {0, 100000, 150000, 200000, 250000, 350000, 500000};
    private String activeSector = "";  // Empty means all sectors.
    private final List<String> sectorChoices = new ArrayList<>();
    private Button loadMoreSales;
    private SimpleAdapter salesAdapter;
    private final List<Map<String,String>> saleRows = new ArrayList<>();
    private final java.util.Set<String> displayedIds = new java.util.HashSet<>();

    // Null means Django has not offered another page.
    private Integer nextSalesPage = null;
    private boolean loadingSales = false;

    /** Connects the XML controls and keeps them clear of the system bars. */
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WindowCompat.enableEdgeToEdge(getWindow());
        setContentView(R.layout.activity_main);

        View root = findViewById(R.id.main);
        int padding = root.getPaddingLeft();
        ViewCompat.setOnApplyWindowInsetsListener(root,(view, insets) ->{
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars()
            | WindowInsetsCompat.Type.displayCutout());

            view.setPadding(padding + bars.left, padding + bars.top,
                    padding + bars.right, padding + bars.bottom);

            return insets;
        });

        loadSales = findViewById(R.id.loadSales);
        salesStatus = findViewById(R.id.salesStatus);
        salesList = findViewById(R.id.salesList);

        loadMoreSales = findViewById(R.id.loadMoreSales);
        filterSector = findViewById(R.id.filterSector);
        filterSector.setOnClickListener(view -> showSectorPicker());
        filterBudget = findViewById(R.id.filterBudget);
        filterBudget.setOnClickListener(view -> showBudgetPicker());
        clearFilters = findViewById(R.id.clearFilters);
        clearFilters.setOnClickListener(view -> loadSalesPage(1, "", 0));
        // Keep the same adapter when appending so the reader doesn't jump to the top.

        salesList.setItemsCanFocus(true);

        salesAdapter = new SimpleAdapter(this, saleRows,
                R.layout.item_sale_listing,
                new String[]{"sector", "price", "details"},
                new int[]{R.id.cardSector, R.id.cardPrice, R.id.cardDetails}){
            /** Binds both actions to the current listing whenever Android reuses a card. */

            @Override
            public View getView(int position, View convertView, android.view.ViewGroup parent){
                View card = super.getView(position,convertView,parent);
                Map<?,?> listing = (Map<?, ?>) getItem(position);

                String listingId = String.valueOf(listing.get("id"));
                String sector = String.valueOf(listing.get("sector"));
                String price = String.valueOf(listing.get("price"));

                card.setFocusable(true);
                card.setOnClickListener(view -> openSaleAnalysis(listingId));

                Button share = card.findViewById(R.id.shareSale);
                share.setContentDescription("Compartir apartamento en " + sector + ", " + price);
                share.setOnClickListener(view -> shareSaleAnalysis(listingId, sector, price));
                return card;
            }
        };
        salesList.setAdapter(salesAdapter);


        loadSales.setOnClickListener(view -> loadSalesPage(1));
        loadMoreSales.setOnClickListener(view -> {
            if (nextSalesPage != null) loadSalesPage(nextSalesPage);
        });
        // The adapter and pagination controls are ready; open directly on the catalog.
        restoreCatalogFilters();
        loadSalesPage(1);
    }//end of oncreate

    /** Shows the reset action only for an active filter and prevents taps during a request. */
    private void updateClearFiltersButton() {
        boolean hasFilters = !activeSector.isEmpty() || activeBudget > 0;
        clearFilters.setVisibility(hasFilters ? View.VISIBLE : View.GONE);
        clearFilters.setEnabled(hasFilters && !loadingSales);
    }

    /** Restores the last successful filter pair before requesting fresh listings. */
    private void restoreCatalogFilters(){
        Map<?,?> saved = getSharedPreferences(CATALOG_PREFS, MODE_PRIVATE).getAll();
        Object sector = saved.get("sector");
        Object budget = saved.get("budget");

        activeSector = "";
        activeBudget = 0;

        // Ignore incomplete settings or a budget preset no longer offered by the app.
        if (sector instanceof String && budget instanceof Integer){
            for (int preset: BUDGETS){
                if (preset == (Integer) budget){
                    activeSector = ((String) sector).trim();
                    activeBudget = preset;
                    break;
                }
            }
        }//end if
        filterSector.setText(activeSector.isEmpty() ? "Sector: Todos" : "Sector: " + activeSector);
        filterBudget.setText("Precio: " + budgetLabel(activeBudget));
    }//end catalog filters

    /** Remembers the filters Django accepted, including searches with zero matches. */
    private void saveCatalogFilters() {
        getSharedPreferences(CATALOG_PREFS, MODE_PRIVATE)
                .edit()
                .putString("sector", activeSector)
                .putInt("budget", activeBudget)
                .apply();
    }
    /** Opens the selected sale's public InmoData analysis in the phone's browser. */
    private void openSaleAnalysis(String listingId) {
        if(!listingId.matches("[1-9][0-9]*")){
            salesStatus.setText("No se pudo identificar esta propiedad.");
            return;
        }//end if

        Uri page = Uri.parse(HOST + "/propiedades/" + listingId + "/");
        android.content.Intent intent =
                new android.content.Intent(android.content.Intent.ACTION_VIEW, page);

        try {
            startActivity(intent);
        } catch (android.content.ActivityNotFoundException error) {
            salesStatus.setText("No hay un navegador disponible para abrir el análisis.");
        }
    }//end open analisys

    /** Opens Android's share menu with the selected sale's price and public analysis link. */
    private void shareSaleAnalysis(String listingId, String sector, String price) {
        if (!listingId.matches("[1-9][0-9]*")) {
            salesStatus.setText("No se pudo identificar esta propiedad.");
            return;
        }

        String link = HOST + "/propiedades/" + listingId + "/";
        String message = "Apartamento en venta en " + sector + "\n"
                + "Precio publicado: " + price + "\n"
                + "Ver análisis en InmoData: " + link;

        android.content.Intent send = new android.content.Intent(android.content.Intent.ACTION_SEND);
        send.setType("text/plain");
        send.putExtra(android.content.Intent.EXTRA_TEXT, message);

        try {
            startActivity(android.content.Intent.createChooser(send, null));
        } catch (android.content.ActivityNotFoundException error) {
            salesStatus.setText("No hay una aplicación disponible para compartir.");
        }
    }

    /** Offers common USD ceilings and keeps the currently displayed sector. */

    private void showBudgetPicker() {
        if (loadingSales) return;

        String[] labels = new String[BUDGETS.length];
        int checked = 0;

        for (int i = 0; i<BUDGETS.length; i++){
            labels[i] = budgetLabel(BUDGETS[i]);
            if (BUDGETS[i] == activeBudget) checked = i;
        }
        new AlertDialog.Builder(this)
                .setTitle("Precio máximo")
                .setSingleChoiceItems(labels, checked, (dialog, index) -> {
                    dialog.dismiss();
                    int chosen = BUDGETS[index];
                    if (chosen != activeBudget) loadSalesPage(1, activeSector, chosen);
                })
                .setNegativeButton("Cancelar", null)
                .show();
    }//end show budget picker

    /** Formats a budget for display while keeping the API value numeric. */
    private String budgetLabel(int budget) {
        if (budget == 0) return "Sin límite";
        NumberFormat format = NumberFormat.getIntegerInstance(Locale.forLanguageTag("es-DO"));
        return "Hasta US$ " + format.format(budget);
    }

    /** Opens a picker populated from all eligible public sales, not just visible cards. */

    private void showSectorPicker() {
        if (loadingSales) return;

        List<String> labels = new ArrayList<>();
        labels.add("Todos los sectores");
        labels.addAll(sectorChoices);

        int checked = activeSector.isEmpty() ? 0 : labels.indexOf(activeSector);

        new AlertDialog.Builder(this)
                .setTitle("seleccionar sector")
                .setSingleChoiceItems(labels.toArray(new String[0]), checked,(dialog,index) ->{
                    dialog.dismiss();
                    String chosen = index ==0 ? "" : labels.get(index);
                    if (!chosen.equals(activeSector)){
                        loadSalesPage(1, chosen, activeBudget);
                    }
                })
                .setNegativeButton("cancelar", null)
                .show();

    }//end show sectgor

    /** Keeps the current sector when the user taps Actualizar or Cargar más. */
    private void loadSalesPage(int pageNumber) {
        loadSalesPage(pageNumber, activeSector, activeBudget);
    }
    /** Loads one page for both requested filters and commits them only after success. */
    private void loadSalesPage(int pageNumber, String requestedSector, int requestedBudget) {
        if (loadingSales) return;
        loadingSales = true;
        updateClearFiltersButton();
        filterSector.setEnabled(false);
        filterBudget.setEnabled(false);

        boolean refreshing = pageNumber ==1;
        loadSales.setEnabled(false);
        loadMoreSales.setEnabled(false);
        salesStatus.setText(refreshing
                ? "Cargando apartamentos…"
                : "Cargando más apartamentos…"
        );

        network.execute(() ->{
            try{
                Uri.Builder url = android.net.Uri.parse(SALES_URL).buildUpon()
                        .appendQueryParameter("page", String.valueOf(pageNumber));
                if (!requestedSector.isEmpty()) url.appendQueryParameter("sector", requestedSector);
                if (requestedBudget > 0) {
                    url.appendQueryParameter("max_price", String.valueOf(requestedBudget));
                }
                if (refreshing) url.appendQueryParameter("include_sectors", "1");

                JSONObject page = readJson(url.build().toString());
                List<String> incomingSectors = new ArrayList<>();
                if (refreshing){
                    JSONArray sectors = page.getJSONArray("sectors");
                    for (int i =0; i < sectors.length(); i++){
                        incomingSectors.add(sectors.getString(i));
                    }
                }
                JSONArray listings = page.getJSONArray("results");
                int total = page.getInt("count");
                Integer followingPage = page.isNull("next_page")
                        ? null : Integer.valueOf(page.getInt("next_page"));

                // Prepare the entire page before changing anything already on screen.
                List<Map<String,String>> incoming = new ArrayList<>();
                NumberFormat numbers = NumberFormat.getNumberInstance(
                        Locale.forLanguageTag("es-DO"));
                numbers.setMaximumFractionDigits(2);

                for (int i=0; i< listings.length(); i++){
                    JSONObject item = listings.getJSONObject(i);
                    Map<String,String> row = new HashMap<>();
                    row.put("id", String.valueOf(item.getLong("id")));
                    row.put("sector", item.getString("sector"));
                    row.put("price", "US$ " + amount(item, "price", numbers));
                    row.put("details",
                            bedroomLabel(item.optInt("bedrooms", 0))
                                    + "  ·  " + amount(item, "area_m2", numbers) + " m²"
                                    + "\nUS$ " + amount(item, "price_per_m2", numbers) + "/m²");
                    incoming.add(row);
                }//end for

                runOnUiThread(() ->{
                    if (isFinishing() || isDestroyed()) return;
                    if (refreshing){
                        saleRows.clear();
                        displayedIds.clear();
                        activeSector = requestedSector;
                        activeBudget = requestedBudget;
                        saveCatalogFilters();
                        filterBudget.setText("Precio: " + budgetLabel(activeBudget));
                        sectorChoices.clear();
                        sectorChoices.addAll(incomingSectors);
                        filterSector.setText(activeSector.isEmpty() ? "Sector: Todos" : "Sector: " + activeSector);
                    }//end if

                    for (Map<String,String> row : incoming){
                        if (displayedIds.add(row.get("id"))) saleRows.add(row);
                    }//end for

                    nextSalesPage = followingPage;
                    salesAdapter.notifyDataSetChanged();
                    if (refreshing && !saleRows.isEmpty()) salesList.setSelection(0);

                    salesStatus.setText(saleRows.isEmpty()
                            ? "No hay apartamentos en venta disponibles."
                            : "Mostrando " + saleRows.size() + " de " + total + " apartamentos.");
                    loadSales.setText("Actualizar");
                    loadMoreSales.setText("Cargar más");
                    loadMoreSales.setVisibility(nextSalesPage == null? View.GONE : View.VISIBLE);
                    loadMoreSales.setEnabled(nextSalesPage != null);
                    loadSales.setEnabled(true);
                    filterSector.setEnabled(!sectorChoices.isEmpty() || !activeSector.isEmpty());
                    loadingSales = false;
                    updateClearFiltersButton();
                    filterBudget.setEnabled(true);
                });//end run ui thread
            }catch (IOException | JSONException | NumberFormatException error){
                Log.w("InmoData", "Could not load sales page " + pageNumber, error);
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;

                    if (!requestedSector.equals(activeSector ) || requestedBudget != activeBudget) {
                        salesStatus.setText("No se cambiaron los filtros. Intenta de nuevo.");
                    } else if (refreshing) {
                        salesStatus.setText("No se pudo actualizar el catálogo. Intenta de nuevo.");
                        loadSales.setText("Reintentar");
                    } else {
                        salesStatus.setText("No se pudo cargar la siguiente página. Tus resultados siguen aquí.");
                        loadMoreSales.setText("Reintentar · Cargar más");
                    }

                    loadSales.setEnabled(true);
                    loadMoreSales.setEnabled(nextSalesPage != null);
                    filterSector.setEnabled(!sectorChoices.isEmpty() || !activeSector.isEmpty());
                    loadingSales = false;
                    updateClearFiltersButton();
                    filterBudget.setEnabled(true);
            });
            }//end try
        });//end network execute

    }// end laod first

    /** Formats the reported bedroom count; zero or missing does not imply a studio. */
    private static String bedroomLabel(int bedrooms) {
        if (bedrooms <= 0) return "Habitaciones: sin dato";
        return bedrooms == 1 ? "1 habitación" : bedrooms + " habitaciones";
    }
    /** Formats Django's decimal strings without converting prices to floating-point numbers. */
    private String amount(JSONObject item, String key, NumberFormat format)
        throws JSONException {
            return format.format(new BigDecimal(item.getString(key)));
    }//end amount


    /** Reads one HTTPS JSON response and releases the connection on success or failure. */
    private JSONObject readJson(String address) throws IOException,JSONException {
        HttpsURLConnection connection =
                (HttpsURLConnection) new URL(address).openConnection();

        try {
            connection.setConnectTimeout(15000);
            connection.setReadTimeout(45000);
            connection.setUseCaches(false);
            connection.setRequestProperty("Accept", "application/json");

            int status = connection.getResponseCode();
            if (status != 200) throw new IOException("HTTP " + status);

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    connection.getInputStream(), StandardCharsets.UTF_8
            ))){
                StringBuilder body = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) body.append(line);
                return new JSONObject(body.toString());

            }//end try
        }finally {
            connection.disconnect();
        }//edn try
    }//end json object

    /** Stops this activity's network worker when the screen is destroyed. */
    @Override
    protected void onDestroy() {
        network.shutdownNow();
        super.onDestroy();
    }


}//end of clas