# -*- coding: utf-8 -*-
"""
Pruning Tutorial
=====================================
**Author**: `Michela Paganini <https://github.com/mickypaganini>`_

State-of-the-art deep learning techniques rely on over-parametrized models 
that are hard to deploy. On the contrary, biological neural networks are 
known to use efficient sparse connectivity. Identifying optimal  
techniques to compress models by reducing the number of parameters in them is 
important in order to reduce memory, battery, and hardware consumption without 
sacrificing accuracy. This in turn allows you to deploy lightweight models on device, and guarantee 
privacy with private on-device computation. On the research front, pruning is 
used to investigate the differences in learning dynamics between 
over-parametrized and under-parametrized networks, to study the role of lucky 
sparse subnetworks and initializations
("`lottery tickets <https://arxiv.org/abs/1803.03635>`_") as a destructive 
neural architecture search technique, and more.

In this tutorial, you will learn how to use ``torch.nn.utils.prune`` to 
sparsify your neural networks, and how to extend it to implement your 
own custom pruning technique.

Requirements
------------
``"torch>=1.4.0a0+8e8a5e0"``

"""
import torch
from torch import nn
import torch.nn.utils.prune as prune
import torch.nn.functional as F

######################################################################
# Create a model
# --------------
#
# In this tutorial, we use the `LeNet 
# <http://yann.lecun.com/exdb/publis/pdf/lecun-98.pdf>`_ architecture from 
# LeCun et al., 1998.

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class LeNet(nn.Module):
    def __init__(self):
        super(LeNet, self).__init__()
        # 1 input image channel, 6 output channels, 3x3 square conv kernel
        self.conv1 = nn.Conv2d(1, 6, 3)
        self.conv2 = nn.Conv2d(6, 16, 3)
        self.fc1 = nn.Linear(16 * 5 * 5, 120)  # 5x5 image dimension
        self.fc2 = nn.Linear(120, 84)
        self.fc3 = nn.Linear(84, 10)

    def forward(self, x):
        x = F.max_pool2d(F.relu(self.conv1(x)), (2, 2))
        x = F.max_pool2d(F.relu(self.conv2(x)), 2)
        x = x.view(-1, int(x.nelement() / x.shape[0]))
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

model = LeNet().to(device=device)


######################################################################
# Inspect a Module
# ----------------
# 
# Let's inspect the (unpruned) ``conv1`` layer in our LeNet model. It will contain two 
# parameters ``weight`` and ``bias``, and no buffers, for now.
module = model.conv1
print(list(module.named_parameters()))

######################################################################
print(list(module.named_buffers()))

######################################################################
# Pruning a Module
# ----------------
# 
# To prune a module (in this example, the ``conv1`` layer of our LeNet 
# architecture), first select a pruning technique among those available in 
# ``torch.nn.utils.prune`` (or
# `implement <#extending-torch-nn-utils-pruning-with-custom-pruning-functions>`_
# your own by subclassing 
# ``BasePruningMethod``). Then, specify the module and the name of the parameter to 
# prune within that module. Finally, using the adequate keyword arguments 
# required by the selected pruning technique, specify the pruning parameters.
#
# In this example, we will prune at random 30% of the connections in 
# the parameter named ``weight`` in the ``conv1`` layer.
# The module is passed as the first argument to the function; ``name`` 
# identifies the parameter within that module using its string identifier; and 
# ``amount`` indicates either the percentage of connections to prune (if it 
# is a float between 0. and 1.), or the absolute number of connections to 
# prune (if it is a non-negative integer).
prune.random_unstructured(module, name="weight", amount=0.3) 

######################################################################
# Pruning acts by removing ``weight`` from the parameters and replacing it with 
# a new parameter called ``weight_orig`` (i.e. appending ``"_orig"`` to the 
# initial parameter ``name``). ``weight_orig`` stores the unpruned version of 
# the tensor. The ``bias`` was not pruned, so it will remain intact.
print(list(module.named_parameters()))

######################################################################
# The pruning mask generated by the pruning technique selected above is saved 
# as a module buffer named ``weight_mask`` (i.e. appending ``"_mask"`` to the 
# initial parameter ``name``).
print(list(module.named_buffers()))

######################################################################
# For the forward pass to work without modification, the ``weight`` attribute 
# needs to exist. The pruning techniques implemented in 
# ``torch.nn.utils.prune`` compute the pruned version of the weight (by 
# combining the mask with the original parameter) and store them in the 
# attribute ``weight``. Note, this is no longer a parameter of the ``module``,
# it is now simply an attribute.
print(module.weight)

######################################################################
# Finally, pruning is applied prior to each forward pass using PyTorch's
# ``forward_pre_hooks``. Specifically, when the ``module`` is pruned, as we 
# have done here, it will acquire a ``forward_pre_hook`` for each parameter 
# associated with it that gets pruned. In this case, since we have so far 
# only pruned the original parameter named ``weight``, only one hook will be
# present.
print(module._forward_pre_hooks)

######################################################################
# For completeness, we can now prune the ``bias`` too, to see how the 
# parameters, buffers, hooks, and attributes of the ``module`` change.
# Just for the sake of trying out another pruning technique, here we prune the 
# 3 smallest entries in the bias by L1 norm, as implemented in the 
# ``l1_unstructured`` pruning function.
prune.l1_unstructured(module, name="bias", amount=3)

######################################################################
# We now expect the named parameters to include both ``weight_orig`` (from 
# before) and ``bias_orig``. The buffers will include ``weight_mask`` and 
# ``bias_mask``. The pruned versions of the two tensors will exist as 
# module attributes, and the module will now have two ``forward_pre_hooks``.
print(list(module.named_parameters()))

######################################################################
print(list(module.named_buffers()))

######################################################################
print(module.bias)

######################################################################
print(module._forward_pre_hooks)

######################################################################
# Iterative Pruning
# -----------------
# 
# The same parameter in a module can be pruned multiple times, with the 
# effect of the various pruning calls being equal to the combination of the
# various masks applied in series.
# The combination of a new mask with the old mask is handled by the 
# ``PruningContainer``'s ``compute_mask`` method.
#
# Say, for example, that we now want to further prune ``module.weight``, this
# time using structured pruning along the 0th axis of the tensor (the 0th axis 
# corresponds to the output channels of the convolutional layer and has 
# dimensionality 6 for ``conv1``), based on the channels' L2 norm. This can be 
# achieved using the ``ln_structured`` function, with ``n=2`` and ``dim=0``.
prune.ln_structured(module, name="weight", amount=0.5, n=2, dim=0)

# As we can verify, this will zero out all the connections corresponding to 
# 50% (3 out of 6) of the channels, while preserving the action of the 
# previous mask.
print(module.weight)

############################################################################
# The corresponding hook will now be of type 
# ``torch.nn.utils.prune.PruningContainer``, and will store the history of 
# pruning applied to the ``weight`` parameter.
for hook in module._forward_pre_hooks.values():
    if hook._tensor_name == "weight":  # select out the correct hook
        break

print(list(hook))  # pruning history in the container 

######################################################################
# Serializing a pruned model
# --------------------------
# All relevant tensors, including the mask buffers and the original parameters
# used to compute the pruned tensors are stored in the model's ``state_dict`` 
# and can therefore be easily serialized and saved, if needed.
print(model.state_dict().keys())


######################################################################
# Remove pruning re-parametrization
# ---------------------------------
#
# To make the pruning permanent, remove the re-parametrization in terms
# of ``weight_orig`` and ``weight_mask``, and remove the ``forward_pre_hook``,
# we can use the ``remove`` functionality from ``torch.nn.utils.prune``.
# Note that this doesn't undo the pruning, as if it never happened. It simply 
# makes it permanent, instead, by reassigning the parameter ``weight`` to the 
# model parameters, in its pruned version.

######################################################################
# Prior to removing the re-parametrization:
print(list(module.named_parameters()))
######################################################################
print(list(module.named_buffers()))
######################################################################
print(module.weight)

######################################################################
# After removing the re-parametrization:
prune.remove(module, 'weight')
print(list(module.named_parameters()))
######################################################################
print(list(module.named_buffers()))

######################################################################
# Pruning multiple parameters in a model 
# --------------------------------------
#
# By specifying the desired pruning technique and parameters, we can easily 
# prune multiple tensors in a network, perhaps according to their type, as we 
# will see in this example.

new_model = LeNet()
for name, module in new_model.named_modules():
    # prune 20% of connections in all 2D-conv layers 
    if isinstance(module, torch.nn.Conv2d):
        prune.l1_unstructured(module, name='weight', amount=0.2)
    # prune 40% of connections in all linear layers 
    elif isinstance(module, torch.nn.Linear):
        prune.l1_unstructured(module, name='weight', amount=0.4)

print(dict(new_model.named_buffers()).keys())  # to verify that all masks exist

######################################################################
# Global pruning
# --------------
#
# So far, we only looked at what is usually referred to as "local" pruning,
# i.e. the practice of pruning tensors in a model one by one, by 
# comparing the statistics (weight magnitude, activation, gradient, etc.) of 
# each entry exclusively to the other entries in that tensor. However, a 
# common and perhaps more powerful technique is to prune the model all at 
# once, by removing (for example) the lowest 20% of connections across the 
# whole model, instead of removing the lowest 20% of connections in each 
# layer. This is likely to result in different pruning percentages per layer.
# Let's see how to do that using ``global_unstructured`` from 
# ``torch.nn.utils.prune``.

model = LeNet()

parameters_to_prune = (
    (model.conv1, 'weight'),
    (model.conv2, 'weight'),
    (model.fc1, 'weight'),
    (model.fc2, 'weight'),
    (model.fc3, 'weight'),
)

prune.global_unstructured(
    parameters_to_prune,
    pruning_method=prune.L1Unstructured,
    amount=0.2,
)

######################################################################
# Now we can check the sparsity induced in every pruned parameter, which will 
# not be equal to 20% in each layer. However, the global sparsity will be 
# (approximately) 20%.
print(
    "Sparsity in conv1.weight: {:.2f}%".format(
        100. * float(torch.sum(model.conv1.weight == 0))
        / float(model.conv1.weight.nelement())
    )
)
print(
    "Sparsity in conv2.weight: {:.2f}%".format(
        100. * float(torch.sum(model.conv2.weight == 0))
        / float(model.conv2.weight.nelement())
    )
)
print(
    "Sparsity in fc1.weight: {:.2f}%".format(
        100. * float(torch.sum(model.fc1.weight == 0))
        / float(model.fc1.weight.nelement())
    )
)
print(
    "Sparsity in fc2.weight: {:.2f}%".format(
        100. * float(torch.sum(model.fc2.weight == 0))
        / float(model.fc2.weight.nelement())
    )
)
print(
    "Sparsity in fc3.weight: {:.2f}%".format(
        100. * float(torch.sum(model.fc3.weight == 0))
        / float(model.fc3.weight.nelement())
    )
)
print(
    "Global sparsity: {:.2f}%".format(
        100. * float(
            torch.sum(model.conv1.weight == 0)
            + torch.sum(model.conv2.weight == 0)
            + torch.sum(model.fc1.weight == 0)
            + torch.sum(model.fc2.weight == 0)
            + torch.sum(model.fc3.weight == 0)
        )
        / float(
            model.conv1.weight.nelement()
            + model.conv2.weight.nelement()
            + model.fc1.weight.nelement()
            + model.fc2.weight.nelement()
            + model.fc3.weight.nelement()
        )
    )
)


######################################################################
# Extending ``torch.nn.utils.prune`` with custom pruning functions
# ------------------------------------------------------------------
# To implement your own pruning function, you can extend the
# ``nn.utils.prune`` module by subclassing the ``BasePruningMethod``
# base class, the same way all other pruning methods do. The base class
# implements the following methods for you: ``__call__``, ``apply_mask``,
# ``apply``, ``prune``, and ``remove``. Beyond some special cases, you shouldn't
# have to reimplement these methods for your new pruning technique.
# You will, however, have to implement ``__init__`` (the constructor),
# and ``compute_mask`` (the instructions on how to compute the mask
# for the given tensor according to the logic of your pruning
# technique). In addition, you will have to specify which type of
# pruning this technique implements (supported options are ``global``,
# ``structured``, and ``unstructured``). This is needed to determine
# how to combine masks in the case in which pruning is applied
# iteratively. In other words, when pruning a prepruned parameter,
# the current pruning technique is expected to act on the unpruned
# portion of the parameter. Specifying the ``PRUNING_TYPE`` will
# enable the ``PruningContainer`` (which handles the iterative
# application of pruning masks) to correctly identify the slice of the
# parameter to prune.
#
# Let's assume, for example, that you want to implement a pruning
# technique that prunes every other entry in a tensor (or -- if the
# tensor has previously been pruned -- in the remaining unpruned
# portion of the tensor). This will be of ``PRUNING_TYPE='unstructured'``
# because it acts on individual connections in a layer and not on entire
# units/channels (``'structured'``), or across different parameters
# (``'global'``).

class FooBarPruningMethod(prune.BasePruningMethod):
    """Prune every other entry in a tensor
    """
    PRUNING_TYPE = 'unstructured'

    def compute_mask(self, t, default_mask):
        mask = default_mask.clone()
        mask.view(-1)[::2] = 0 
        return mask

######################################################################
# Now, to apply this to a parameter in an ``nn.Module``, you should
# also provide a simple function that instantiates the method and
# applies it.
def foobar_unstructured(module, name):
    """Prunes tensor corresponding to parameter called `name` in `module`
    by removing every other entry in the tensors.
    Modifies module in place (and also return the modified module) 
    by:
    1) adding a named buffer called `name+'_mask'` corresponding to the 
    binary mask applied to the parameter `name` by the pruning method.
    The parameter `name` is replaced by its pruned version, while the 
    original (unpruned) parameter is stored in a new parameter named 
    `name+'_orig'`.

    Args:
        module (nn.Module): module containing the tensor to prune
        name (string): parameter name within `module` on which pruning
                will act.

    Returns:
        module (nn.Module): modified (i.e. pruned) version of the input
            module
    
    Examples:
        >>> m = nn.Linear(3, 4)
        >>> foobar_unstructured(m, name='bias')
    """
    FooBarPruningMethod.apply(module, name)
    return module

######################################################################
# Let's try it out!
model = LeNet()
foobar_unstructured(model.fc3, name='bias')

print(model.fc3.bias_mask)
