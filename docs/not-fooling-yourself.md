# Come non ingannare te stesso col backtesting

Un backtest brillante non significa una strategia profittevole. È il modo più facile per illudersi in finanza algoritmica. Alcune trappole comuni — e come GlassBox cerca di proteggerti da loro.

## 1. Overfitting

Un modello (specialmente il Bot 1 ML) può imparare a memoria le coincidenze del passato invece di un pattern reale. Più parametri liberi ha un modello, più facile cade in questa trappola.

**Cosa fa GlassBox**: target binario semplice (su/giù, non un prezzo esatto), modelli interpretabili di default (Random Forest, Logistic Regression — non reti neurali), validazione walk-forward obbligatoria.

**Cosa puoi fare tu**: non fidarti di un singolo backtest con risultati eccezionali. Prova periodi diversi, asset diversi. Se la performance crolla cambiando leggermente la finestra temporale, era overfitting.

## 2. Data leakage (mescolare passato e futuro)

Se il modello vede, anche indirettamente, dati che nella realtà non avrebbe ancora avuto, il backtest mente.

**Cosa fa GlassBox**: `MarketContext` porta solo dati fino all'istante corrente incluso. Il training del Bot 1 esclude sempre la barra più recente dal training set (la sua label dipende dal futuro). Vedi il test `test_last_bar_excluded_from_training`.

## 3. Il simulatore troppo gentile

Un broker simulato che esegue sempre al prezzo esatto, senza fee né slippage, fa sembrare profittevole quasi ogni strategia che fa molti trade piccoli.

**Cosa fa GlassBox**: fee e slippage sono **sempre applicati**, configurabili dall'utente ma non disattivabili a zero per sbaglio nella UI di default.

## 4. Survivorship e selection bias

Se scegli gli asset *dopo* aver visto come sono andati, hai già barato.

**Cosa puoi fare tu**: decidi gli asset *prima* di guardare il backtest, e tienili fissi per il confronto tra i tre bot.

## 5. Il mercato reale non è il backtest

Anche un backtest "pulito" non cattura latenza, illiquidità, eventi improvvisi, cambi di regime. Un risultato simulato — anche ottimo — **non predice performance reali**.

**La regola d'oro**: usa GlassBox per imparare *come* funzionano le strategie e *quali errori evitare*, non come prova che una strategia "funziona".
