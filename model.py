import numpy as np
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.nn.functional as F

from utils import set_seed


class Model(nn.Module):
    def __init__(self, config):
        super().__init__()

        self.config = config
        self.build_model()
        self.init_parameters()
    


    def train_model(self, train_loader, valid_loader, test_loader, device):
        ######################################################################################
        #                                                                                    #
        #                               Main Training Loop for all models                    #
        #                                                                                    #
        ##################################    Initializations    #############################
    

        set_seed(self.config.seed)

        # returns a list of optimizers for different groups of parameters
        optimizers = self.optimizers()
 
        ##################################    Train Loop    ##################################

        loss_epochs = {'train':[], 'valid':[] , 'test':[]}
        metric_epochs = {'train':[], 'valid':[], 'test':[]}
        best_metric_val, best_metric_test, best_loss_val = 0, 0, 1e6

        for epoch in range(self.config.epochs):
            self.train()
            
            loss_batch, metric_batch = [], []
            for i, (x, labels, _ ) in enumerate(tqdm(train_loader)):                  # _ is the length of unpadded x

                # x for shd is: (batch_size, time_steps, neurons)
                labels = F.one_hot(labels, self.config.n_outputs).float()

                x = x.to(device)
                labels = labels.to(device)

                for opt in optimizers:  opt.zero_grad()

                output = self.forward(x)
                loss = self.calc_loss(output, labels)

                loss.backward()
                for opt in optimizers: opt.step()

                metric = self.calc_metric(output, labels)

                loss_batch.append(loss.detach().cpu().item())
                metric_batch.append(metric)

                self.reset_model()
                
            loss_epochs['train'].append(np.mean(loss_batch))
            metric_epochs['train'].append(np.mean(metric_batch))

            ##################################    Eval Loop    ##################################

            loss_valid, metric_valid = self.eval_model(valid_loader, device)

            loss_epochs['valid'].append(loss_valid)
            metric_epochs['valid'].append(metric_valid)


            if test_loader:
                loss_test, metric_test = self.eval_model(test_loader, device)
            else:
                # could be improved
                loss_test, metric_test = 100, 0
            loss_epochs['test'].append(loss_test)
            metric_epochs['test'].append(metric_test)

            ##########################     Logging and Plotting  ################################

            print(f"=====> Epoch {epoch} : \nLoss Train = {loss_epochs['train'][-1]:.3f}  |  Acc Train = {100*metric_epochs['train'][-1]:.2f}%")
            print(f"Loss Valid = {loss_epochs['valid'][-1]:.3f}  |  Acc Valid = {100*metric_epochs['valid'][-1]:.2f}%  |  Best Acc Valid = {100*max(metric_epochs['valid'][-1], best_metric_val):.2f}%")

            if test_loader:
                print(f"Loss Test = {loss_epochs['test'][-1]:.3f}  |  Acc Test = {100*metric_epochs['test'][-1]:.2f}%  |  Best Acc Test = {100*max(metric_epochs['test'][-1], best_metric_test):.2f}%")

                

    def eval_model(self, loader, device):
        
        self.eval()
        with torch.no_grad():
            loss_batch, metric_batch = [], []
            for i, (x, labels, _ ) in enumerate(tqdm(loader)):                        # _ is the length of unpadded x

                # x for shd is: (batch_size, time_steps, neurons)
                labels = F.one_hot(labels, self.config.n_outputs).float()

                x = x.to(device)
                labels = labels.to(device)

                output = self.forward(x)

                loss = self.calc_loss(output, labels)
                metric = self.calc_metric(output, labels)

                loss_batch.append(loss.detach().cpu().item())
                metric_batch.append(metric)

                self.reset_model()

        
        return np.mean(loss_batch), np.mean(metric_batch)
    

    def calc_loss(self, output, y):

        if self.config.loss == 'mean': m = torch.mean(output, 0)
        elif self.config.loss == 'max': m, _ = torch.max(output, 0)
        elif self.config.loss == 'spike_count': m = torch.sum(output, 0)
        elif self.config.loss == 'sum':
            softmax_fn = nn.Softmax(dim=2)
            m = torch.sum(softmax_fn(output), 0)

        
        if self.config.loss_fn == 'CEloss':
            CEloss = nn.CrossEntropyLoss()
            loss = CEloss(m, y)
        
        return loss
    

    def calc_metric(self, output, y):
        if self.config.loss == 'mean': m = torch.mean(output, 0)
        elif self.config.loss == 'max': m, _ = torch.max(output, 0)
        elif self.config.loss == 'spike_count': m = torch.sum(output, 0)
        elif self.config.loss == 'sum':
            softmax_fn = nn.Softmax(dim=2)
            m = torch.sum(softmax_fn(output), 0)

        return np.mean((torch.max(y,1)[1]==torch.max(m,1)[1]).detach().cpu().numpy())