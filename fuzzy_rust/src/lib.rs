use fuzzy_matcher::skim::SkimMatcherV2;
use fuzzy_matcher::FuzzyMatcher;
use pyo3::prelude::*;
use pyo3::types::PyList;
use rayon::prelude::*;

/// Perform fuzzy matching on input search terms and return top results.
#[pyfunction]
fn extract_bests<'a>(
    query: &str,
    // search_terms: &Bound<'a, PyDict>,
    search_terms: &Bound<'a, PyList>,
    limit: usize,
) -> PyResult<Vec<(String, i64)>> {
    let matcher = SkimMatcherV2::default();
    // let mut results = Vec::new();

    // for term_obj in search_terms.iter() {
    //     let term = term_obj.extract::<&str>()?;
    //     if let Some(score) = matcher.fuzzy_match(term, query) {
    //         results.push((term.to_string(), score));
    //     }
    // }

    let term_list: Vec<String> = search_terms
        .iter()
        .map(|py_s| py_s.extract::<&str>().map(|s| s.to_string()).unwrap())
        .collect();

    let mut results: Vec<(String, i64)> = term_list
        .par_iter()
        .filter_map(|term| {
            matcher
                .fuzzy_match(term, query)
                .map(|score| (term.clone(), score))
        })
        .collect();

    results.sort_by(|a, b| b.1.cmp(&a.1));
    results.truncate(limit);

    Ok(results)
    // Ok(results.into_iter().map(|(a, _)| a).collect())
}

/// A Python module implemented in Rust.
#[pymodule]
fn fuzzy_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(extract_bests, m)?)?;
    Ok(())
}
