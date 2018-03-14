import json
from time import time
import multiprocessing
from collections import defaultdict

import click
import numpy as np
import pandas as pd

from sklearn.pipeline import Pipeline
from sklearn.feature_extraction import DictVectorizer
from sklearn.model_selection import cross_validate, StratifiedKFold
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn_utils.utils import SkUtilsIO

from metabolitics.preprocessing import MetaboliticsPipeline, MetaboliticsTransformer
from metabolitics.utils import load_network_model

from utils import mwtab_to_df


@click.group()
def cli():
    pass


@cli.command()
@click.argument('disease_name')
def analysis_and_save_disease(disease_name):
    path = '../datasets/diseases/%s.csv' % disease_name
    X, y = SkUtilsIO(path).from_csv(label_column='labels')

    pipe = MetaboliticsPipeline([
        'metabolite-name-mapping',
        'standard-scaler',
        'metabolitics-transformer',
    ])
    X_t = pipe.fit_transform(X, y)

    SkUtilsIO('../outputs/%s_analysis_with_std.json' % disease_name,
              gz=True).to_json(X_t, y)


@cli.command()
def bc_performance():
    X, y = SkUtilsIO(
        '../datasets/bc_analysis_with_std.json', gz=True).from_json()

    pipe = Pipeline([
        ('metabolitics', MetaboliticsPipeline([
            'reaction-diff',
            # 'feature-selection',
            'pathway-transformer',
        ])),
        ('vect', DictVectorizer(sparse=False)),
        ('pca', PCA()),
        ('clf', LogisticRegression(C=0.3e-6, random_state=43))
    ])

    kf = StratifiedKFold(n_splits=10, random_state=43)

    cv_score = cross_validate(pipe, X, y, cv=kf, n_jobs=-1, scoring='f1_micro')

    print(cv_score)

    import pdb
    pdb.set_trace()


@cli.command()
@click.argument('disease_name')
def analysis_mwtab(disease_name):
    df = mwtab_to_df('../datasets/diseases/%s.mwtab' % disease_name)
    df.to_csv('../outputs/%s.csv' % disease_name, index=False)


@cli.command()
def parse_naming_files():

    df = pd.read_csv(
        '../datasets/naming/recon-store-metabolites.tsv', sep='\t')

    model = load_network_model('recon2')
    mappings = defaultdict(dict)

    for i, row in df.iterrows():
        m = '%s_c' % row['abbreviation']

        if m not in model.metabolites:
            continue

        for k in row.keys()[1:]:
            if type(row[k]) == str:
                mappings[k][row[k]] = m

    for k, v in mappings.items():
        db = k.replace('Id', '')

        with open('../outputs/%s-mapping.json' % db, 'w') as f:
            json.dump(v, f)


@cli.command()
def coverage_test_generate():

    model = load_network_model('recon2')
    # n = multiprocessing.cpu_count()

    metabolite_ids = list(map(lambda x: x.id, model.metabolites))
    num_metabolite = len(metabolite_ids)

    # X = [
    #     dict(zip(metabolite_ids, np.random.randn(len(metabolite_ids))))
    #     for _ in range(n)
    # ]

    # df = pd.DataFrame.from_records(X)
    # y = np.random.choice(['h', 'x'], n)

    # SkUtilsIO('../outputs/coverage_test#metabolites.json',
    #           gz=True).to_json(X, y)

    X, y = SkUtilsIO('../datasets/coverage_test/coverage_test#metabolites.json',
              gz=True).from_json()
    
    df = pd.DataFrame.from_records(X)
    
    transformer = MetaboliticsTransformer(model)

    t = time()
    # X_ref = transformer.fit_transform(X, y)

    # SkUtilsIO('../outputs/coverage_test#coverage=1.json',
    #           gz=True).to_json(X_ref, y)

    X_ref, _ = SkUtilsIO('../datasets/coverage_test/coverage_test#coverage=1.json',
              gz=True).from_json()

    print('Ref done!')
    print(time() - t)

    for i in range(100):

        for coverage in np.linspace(0.15, 0.05, 3):

            selected_metabolite = np.random.choice(
                df.columns,
                int(np.ceil(num_metabolite * coverage)),
                replace=False)

            t = time()
            X_selected = df[selected_metabolite].to_dict('records')
            X_t = transformer.fit_transform(X_selected, y)
            print(time() - t)

            name = 'coverage=%f#iteration=%d' % (coverage, i)

            SkUtilsIO('../outputs/coverage_test#%s.json' %
                      name, gz=True).to_json(X_t, y)
            print('%s done!' % name)
