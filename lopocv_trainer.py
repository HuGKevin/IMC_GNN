import sys
sys.path.append('/home/kevin/project')

import numpy as np
import torch
from IMC_GNN.models import GCN, GCN_Train
import copy
from sklearn.metrics import roc_auc_score

from torch_geometric.data import Data, Dataset, DataLoader, batch

class LOPOCV():
    
    def __init__(self, model, dataset, devices, batch_size):
        
        self.model_trainers = dict()
        self.train_loaders = dict()
        self.test_loaders = dict()
        self.ground_truth = dict()
        self.device = devices
        self.original_model = model

        self.patient_list = list(set([data.name for data in dataset]))

        for patient in self.patient_list:
            # Get test set, i.e. all graphs associated with this patient
            test_set = [data for data in dataset if data.name == patient]

            # Get training set, i.e. all graphs not associated with this patient
            train_set = [data for data in dataset if data.name != patient]

            # Get ground truth for the patient
            self.ground_truth[patient] = test_set[0].y

            # Create DataLoaders for each set
            self.train_loaders[patient] = DataLoader(train_set, batch_size = batch_size, shuffle = True)
            self.test_loaders[patient] = DataLoader(test_set, batch_size = batch_size, shuffle = False)
                        
            #create model
            self.model_trainers[patient] = copy.deepcopy(self.original_model)
            
    
    def load_model_into_pos(self, file, patient):
        '''
        Loads model from file, (usually will be directory/lopo$(patient).mdl)
        '''
        ###TODO MODEL LOAD FUNC
        self.model_trainers[patient].load_model(file)
        
    def load_all_models_from_dir(self, direc):
        '''
        Load all models from directory, files in format lopo$(patient).mdl
        '''
        for patient in self.patient_list:
            self.load_model_into_pos(direc + 'lopo'+str(patient)+'.mdl', patient)
    
    def train(self, save_dir = None, ignore_es = False, verbose=False):
        '''
        Train all models on appropriate data from train loaders
        '''
        if verbose:
            print("Training all models in LOPO regime...")
            if save_dir is not None:
                print("-saving all models to", save_dir, "with naming conv: lopo$(patient).mdl")
            
        for patient in self.patient_list:
            if verbose:
                print("Leaving patient", patient, "out")
            
            if verbose:
                print("---Selecting device and transferring")
                
            #Pick GPU with largest amount of memory free
            # TODO: implement select_freest_device
            # selected_device = select_freest_device(self.device_pool)
            selected_device = self.device
            if verbose:
                print("---Transferred to device", selected_device)
            
            
            ###TODO: edit device transfer
            self.model_trainers[patient].to(selected_device)
            
            if verbose:
                print("---Starting Train")
                print()
                print()
            
            self.model_trainers[patient].train_epoch(self.train_loaders[patient], verbose = verbose, ignore_es = ignore_es)
            
            if verbose:
                print("---Removing model from device")
            
            
            ###TODO: edit device transfer
            self.model_trainers[patient].model.to('cpu')
            
            if verbose and save_dir is not None:
                print("---Saving model as lopo", patient, ".mdl")

            ###TODO: need model save code
            self.model_trainers[patient].save_model(save_dir + 'lopo' + patient + '.mdl')

    def validate(self, device=None, verbose=False, aggregate_func=None):
        '''
        Validate all models on their respective leave one out patients, and aggregate if needed
        '''
        scores = dict()
        ground_truth = dict()
        for patient in self.patient_list:
            if verbose:
                print("Leaving patient", patient, "out")

            # Move model to device
            selected_device = self.device
            self.model_trainers[patient].to(selected_device)
            
            #validate model
            for data in self.test_loaders[patient]:
                data.to(selected_device)
                scores[patient] = self.model_trainers[patient].predict(data.x, data.edge_index, data.batch)
                        
            # Move model back to cpu
            self.model_trainers[patient].model.to('cpu')

            # Get ground truth in there
            ground_truth[patient] = self.ground_truth[patient].repeat(len(scores[patient]))

        #Aggregate (or don't) the scores and return
        if aggregate_func is None:
            return scores
        elif aggregate_func == 'AUC':
            final_scores = torch.cat(list(scores.values()), dim = 0).to('cpu').detach()
            final_truth = torch.cat(list(ground_truth.values()), dim = 0)
            return roc_auc_score(final_truth, final_scores)
        else:
            if verbose:
                print("Aggregating scores")

            agg_scores = self.aggregate(scores, aggregate_func)

            # Compare aggregate scores against ground truth
            return roc_auc_score([self.ground_truth[patient] for patient in self.ground_truth.keys()],
                                 [agg_scores[patient] for patient in agg_scores.keys()])
            
    
    def predict(self, x, edge_index, device=None, verbose=False, aggregate_func=None):
        '''
        Predict using all models on their respective leave one out patients, and aggregate if needed
        '''
        preds = dict()
        for patient in self.test_loaders:
            if verbose:
                print("Leaving patient", patient, "out")
            #predict with model
            preds[patient] = self.model_trainers[patient].predict(x, edge_index, verbose = verbose)
            
        #Aggregate (or don't) the predictions and return
        if aggregate_func is None:
            return preds
        else:
            if verbose:
                print("Aggregating predictions")
            return aggregate(preds)

    def aggregate(self, scores, func, verbose = False):
        '''
        Aggregates scores from model.validate() such that we can compute a final ROC AUC in validate() or predict()
        '''
        if func == 'majority_vote':
            vals = {patient:np.round(scores[patient]) for patient in scores.keys()}
        if func == 'logit_regression':
            vals = 'coming soon...'
        
        return(vals)

